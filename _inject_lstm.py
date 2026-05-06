import json

with open('Untitled0.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

lines = nb['cells'][0]['source']

# 1. Update deps
for i, line in enumerate(lines):
    if '"fake-useragent", "python-dotenv"' in line:
        lines[i] = line.replace('"python-dotenv"', '"python-dotenv", "torch"')
        break

# 2. Add torch imports
for i, line in enumerate(lines):
    if 'import lightgbm as lgb' in line:
        lines.insert(i, "import torch\nimport torch.nn as nn\nimport torch.optim as optim\nfrom torch.utils.data import TensorDataset, DataLoader\n")
        break

# 3. Locate SentimentClassifier block
start_idx = -1
for i, line in enumerate(lines):
    if 'class SentimentClassifier:' in line:
        start_idx = i
        break

end_idx = -1
for i in range(start_idx, len(lines)):
    if 'BLOCK 15 — EXECUTIVE SUMMARY' in lines[i]:
        end_idx = i - 2
        break

LSTM_CODE = """class BiLSTMClassifier(nn.Module):
    def __init__(self, vocab_size: int, embed_dim=300, hidden_dim=128, num_classes=3):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, num_layers=2, 
                            bidirectional=True, batch_first=True, dropout=0.3)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        embedded = self.embedding(x)
        lstm_out, (hn, cn) = self.lstm(embedded)
        # Use the last hidden state from both directions
        hidden = torch.cat((hn[-2,:,:], hn[-1,:,:]), dim=1)
        hidden = self.dropout(hidden)
        return self.fc(hidden)

class SentimentClassifier:
    \"\"\"Trains and evaluates ML models + BiLSTM for EV sentiment.\"\"\"

    def __init__(self, config: PipelineConfig):
        self._cfg        = config
        self._log        = _build_logger("ev.classifier")
        self._lgb_model  = None
        self._rf_model   = None
        self._vectorizer = None
        self._le         = LabelEncoder()
        
        # LSTM attributes
        self._lstm_model = None
        self._word2idx   = {"<PAD>": 0, "<UNK>": 1}
        self._max_len    = 60
        self._vocab_size = 2
        self._device     = torch.device('mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu')

    def _build_vocab_and_tokenize(self, texts, is_train=True):
        seqs = []
        for text in texts:
            tokens = str(text).split()[:self._max_len]
            if is_train:
                for tok in tokens:
                    if tok not in self._word2idx and len(self._word2idx) < 20000:
                        self._word2idx[tok] = len(self._word2idx)
            seq = [self._word2idx.get(tok, 1) for tok in tokens]
            if len(seq) < self._max_len:
                seq += [0] * (self._max_len - len(seq))
            seqs.append(seq)
        if is_train:
            self._vocab_size = len(self._word2idx)
        return torch.tensor(seqs, dtype=torch.long)

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        self._log.info("Starting classifier training (ML + LSTM)...")
        tdf = df[df.get("is_valid", True) if "is_valid" in df.columns else [True]*len(df)]
        tdf = df[df["processed_text"].str.strip().astype(bool).fillna(False)]
        if len(tdf) < 30:
            self._log.warning("Insufficient data (%d records).", len(tdf))
            return {"error":"insufficient_data"}
            
        X_text = tdf["processed_text"].values
        y_raw  = tdf["sentiment"].values
        self._le.fit(y_raw)
        y = self._le.transform(y_raw)
        self._log.info("Training: %d records | Classes: %s | Device: %s", len(X_text), self._le.classes_.tolist(), self._device)

        # ── 1. TF-IDF ML Pipeline ────────────────────────
        self._vectorizer = TfidfVectorizer(max_features=15000, ngram_range=(1,3), min_df=2, max_df=0.9, sublinear_tf=True)
        X_vec = self._vectorizer.fit_transform(X_text).astype(np.float32)

        try:
            X_tr, X_te, y_tr, y_te, text_tr, text_te = train_test_split(
                X_vec, y, X_text, test_size=0.2, random_state=42, stratify=y)
        except ValueError:
            X_tr, X_te, y_tr, y_te, text_tr, text_te = train_test_split(
                X_vec, y, X_text, test_size=0.2, random_state=42)

        results = {}

        if _LGB:
            self._lgb_model = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.04, max_depth=8, num_leaves=31, class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1, min_child_samples=5)
            self._lgb_model.fit(X_tr, y_tr)
            y_pred = self._lgb_model.predict(X_te)
            acc = accuracy_score(y_te, y_pred)
            f1  = f1_score(y_te, y_pred, average="macro", zero_division=0)
            results["lgbm"] = {"accuracy": round(acc,4), "f1_macro": round(f1,4)}
            self._log.info("LightGBM → Acc=%.4f | F1=%.4f", acc, f1)
        else: y_pred = None

        self._rf_model = RandomForestClassifier(n_estimators=200, max_depth=12, class_weight="balanced", random_state=42, n_jobs=-1)
        X_tr_d = X_tr.toarray() if issparse(X_tr) else X_tr
        X_te_d = X_te.toarray() if issparse(X_te) else X_te
        self._rf_model.fit(X_tr_d, y_tr)
        y_pred_rf = self._rf_model.predict(X_te_d)
        acc_rf = accuracy_score(y_te, y_pred_rf)
        f1_rf  = f1_score(y_te, y_pred_rf, average="macro", zero_division=0)
        results["rf"] = {"accuracy": round(acc_rf,4), "f1_macro": round(f1_rf,4)}
        self._log.info("RandomForest → Acc=%.4f | F1=%.4f", acc_rf, f1_rf)

        # ── 2. BiLSTM Pipeline ───────────────────────────
        self._log.info("Building sequences for Deep Learning...")
        X_lstm_tr = self._build_vocab_and_tokenize(text_tr, is_train=True)
        X_lstm_te = self._build_vocab_and_tokenize(text_te, is_train=False)
        y_lstm_tr = torch.tensor(y_tr, dtype=torch.long)
        y_lstm_te = torch.tensor(y_te, dtype=torch.long)
        
        train_loader = DataLoader(TensorDataset(X_lstm_tr, y_lstm_tr), batch_size=128, shuffle=True)
        test_loader  = DataLoader(TensorDataset(X_lstm_te, y_lstm_te), batch_size=128)
        
        self._lstm_model = BiLSTMClassifier(vocab_size=self._vocab_size).to(self._device)
        optimizer = optim.Adam(self._lstm_model.parameters(), lr=0.002)
        
        # Calculate class weights for imbalance
        class_counts = np.bincount(y_tr)
        weights = torch.tensor([sum(class_counts) / c for c in class_counts], dtype=torch.float32).to(self._device)
        criterion = nn.CrossEntropyLoss(weight=weights)
        
        self._log.info("Pre-training LSTM (Params: ~%.1f M) on 5 Epochs...", sum(p.numel() for p in self._lstm_model.parameters())/1e6)
        
        for epoch in range(5):
            self._lstm_model.train()
            total_loss = 0
            for bx, by in train_loader:
                bx, by = bx.to(self._device), by.to(self._device)
                optimizer.zero_grad()
                out = self._lstm_model(bx)
                loss = criterion(out, by)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                
        # Evaluate LSTM
        self._lstm_model.eval()
        lstm_preds = []
        with torch.no_grad():
            for bx, _ in test_loader:
                bx = bx.to(self._device)
                out = self._lstm_model(bx)
                lstm_preds.extend(torch.argmax(out, dim=1).cpu().tolist())
                
        acc_lstm = accuracy_score(y_te, lstm_preds)
        f1_lstm  = f1_score(y_te, lstm_preds, average="macro", zero_division=0)
        results["lstm"] = {"accuracy": round(acc_lstm,4), "f1_macro": round(f1_lstm,4)}
        self._log.info("BiLSTM → Acc=%.4f | F1=%.4f", acc_lstm, f1_lstm)
        
        # ── 3. Evaluation & Save ────────────────────────
        best_pred   = lstm_preds # Focus visual evaluation on the new LSTM
        class_names = [str(c) for c in self._le.classes_]
        viz = VisualizationSuite.__new__(VisualizationSuite)
        viz._cfg = self._cfg; viz._log = self._log
        viz.chart_18_confusion_matrix(y_te, best_pred, class_names, model_name="BiLSTM")

        if _LGB and self._lgb_model:
            joblib.dump(self._lgb_model, self._cfg.models_dir/"lgbm_sentiment.pkl")
        joblib.dump(self._rf_model,   self._cfg.models_dir/"rf_sentiment.pkl")
        joblib.dump(self._vectorizer, self._cfg.models_dir/"tfidf_vectorizer.pkl")
        joblib.dump(self._le,         self._cfg.models_dir/"label_encoder.pkl")
        
        with open(self._cfg.models_dir/"vocab.json", "w") as f:
            json.dump(self._word2idx, f)
        torch.save(self._lstm_model.state_dict(), self._cfg.models_dir/"lstm_sentiment.pth")
        
        self._log.info("✅ Models (ML + DL) saved to %s", self._cfg.models_dir)

        results["n_train"]  = len(y_tr)
        results["n_test"]   = len(y_te)
        results["classes"]  = self._le.classes_.tolist()
        return results

    def predict(self, texts: List[str]) -> List[Dict]:
        if self._vectorizer is None or self._lstm_model is None:
            raise RuntimeError("Call .train() first.")
        norm = ViTextNormalizer(); seg = ViSegmenter(); sf = StopFilter()
        processed = []
        for t in texts:
            n = norm.normalize(t); s = seg.segment(n); f,_,_ = sf.filter(s)
            processed.append(f)
            
        # Predict with LSTM
        self._lstm_model.eval()
        seqs = self._build_vocab_and_tokenize(processed, is_train=False).to(self._device)
        with torch.no_grad():
            outputs = self._lstm_model(seqs)
            probs = torch.softmax(outputs, dim=1).cpu().numpy()
            preds = np.argmax(probs, axis=1)
            
        return [
            {"text": t, "sentiment": int(self._le.inverse_transform([p])[0]),
             "confidence": round(float(probs[i].max()),4)}
            for i, (t,p) in enumerate(zip(texts, preds))
        ]
"""

# Convert LSTM code to a list of lines with \n
lstm_lines = [l + '\n' for l in LSTM_CODE.split('\n')]

# Splice
lines = lines[:start_idx] + lstm_lines + lines[end_idx:]

nb['cells'][0]['source'] = lines

with open('Untitled0.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("LSTM Injection Successful!")
