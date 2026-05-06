"""EV Sentiment ABSA Dashboard — Premium UI v2"""
import streamlit as st, pandas as pd, numpy as np, sys
import plotly.express as px, plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

st.set_page_config(page_title="EV Sentiment · ABSA", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

BC = {"VinFast":"#00E676","BYD":"#448AFF","Mixed":"#FFD740","Unknown":"#78909C","Tesla":"#FF5252","Wuling":"#FF6E40","MG":"#CE93D8"}
AC = {"BATTERY_CHARGING":"#FF6B6B","SOFTWARE_TECHNOLOGY":"#4ECDC4","PERFORMANCE_DRIVING":"#45B7D1","DESIGN_INTERIOR":"#96CEB4","SERVICE_AFTERSALES":"#FFEAA7","PRICE_VALUE":"#DDA0DD"}
AL = {"BATTERY_CHARGING":"🔋 Battery","SOFTWARE_TECHNOLOGY":"💻 Software","PERFORMANCE_DRIVING":"🏎️ Performance","DESIGN_INTERIOR":"🎨 Design","SERVICE_AFTERSALES":"🛠️ Service","PRICE_VALUE":"💰 Price"}
SM = {1:"Positive",0:"Neutral",-1:"Negative"}
SC = {"Positive":"#00E676","Neutral":"#78909C","Negative":"#FF5252"}
DP = Path("artifacts/processed/ev_corpus_preprocessed_v4.parquet")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*{font-family:'Inter',sans-serif!important}

/* ═══ GLOBAL DARK BG ═══ */
html,body,.main,.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"],
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
header,footer,.viewerBadge_container__r5tak,
[data-testid="stAppViewBlockContainer"]{
  background:linear-gradient(160deg,#0a0e27 0%,#0f1535 40%,#131a3d 70%,#0d1230 100%)!important;
  color:#e8eaed!important}
[data-testid="stSidebar"],[data-testid="stSidebarContent"]{
  background:linear-gradient(180deg,#0d1230,#141b3d,#0a0e27)!important;
  border-right:1px solid rgba(100,120,255,.12)!important}
[data-testid="stSidebar"] *,[data-testid="stSidebarContent"] *{color:#d0d4da!important}
[data-testid="stBottom"]{background:transparent!important}
[data-testid="stHeader"]{background:transparent!important}
.block-container{padding:1.5rem 2rem!important;max-width:100%!important}

/* ═══ SCROLLBAR ═══ */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:rgba(10,14,39,.6);border-radius:8px}
::-webkit-scrollbar-thumb{background:linear-gradient(180deg,#448AFF,#7C4DFF);border-radius:8px}
::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,#5C9AFF,#9C6DFF)}
*{scrollbar-width:thin;scrollbar-color:#448AFF rgba(10,14,39,.6)}

/* ═══ TYPOGRAPHY ═══ */
h1{background:linear-gradient(135deg,#00E676,#448AFF,#CE93D8);-webkit-background-clip:text;
  -webkit-text-fill-color:transparent;font-weight:900!important;font-size:2.2rem!important;letter-spacing:-1px}
h2{color:#e0e7ff!important;font-weight:700!important;font-size:1.4rem!important;
  border-bottom:2px solid rgba(100,120,255,.15);padding-bottom:8px;margin-top:24px}
h3{color:#e0e4ff!important;font-weight:600!important;font-size:1.15rem!important}
p,span,label,div,li,td,th{color:#e0e3e8!important;font-size:0.95rem}

/* ═══ ALL INPUTS / WIDGETS DARK ═══ */
input,select,textarea,[data-baseweb="input"],[data-baseweb="select"],
[data-baseweb="textarea"],[data-baseweb="base-input"],
.stSelectbox div[data-baseweb="select"]>div,
.stMultiSelect div[data-baseweb="select"]>div,
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"]>div,
[role="listbox"],[role="option"],
ul[data-testid="stVirtualDropdown"],
div[data-baseweb="popover"]>div>div,
div[data-baseweb="popover"]>div>div>ul{
  background:#141b3d!important;color:#e0e7ff!important;
  border-color:rgba(100,120,255,.2)!important}
[role="option"]:hover,[data-baseweb="menu"] li:hover{
  background:rgba(68,138,255,.2)!important}
[data-baseweb="tag"]{background:rgba(68,138,255,.25)!important;
  border:1px solid rgba(68,138,255,.3)!important;border-radius:8px!important}
[data-baseweb="tag"] span{color:#82B1FF!important}
.stSelectbox>div>div,.stMultiSelect>div>div{
  background:rgba(20,27,61,.8)!important;border:1px solid rgba(100,120,255,.2)!important;border-radius:10px!important}
.stTextInput>div>div>input{background:rgba(20,27,61,.8)!important;
  border:1px solid rgba(100,120,255,.2)!important;border-radius:10px!important;color:#e0e7ff!important}
.stTextArea textarea{background:rgba(20,27,61,.8)!important;
  border:1px solid rgba(100,120,255,.2)!important;border-radius:12px!important;color:#e0e7ff!important}
.stTextArea textarea:focus,.stTextInput>div>div>input:focus{
  border-color:rgba(68,138,255,.5)!important;box-shadow:0 0 20px rgba(68,138,255,.12)!important}

/* ═══ DATAFRAME / TABLE ═══ */
[data-testid="stDataFrame"]{border:1px solid rgba(100,120,255,.15)!important;border-radius:12px!important}
[data-testid="stDataFrame"] th{color:#e0e7ff!important;font-weight:700!important}
[data-testid="stDataFrame"] td{color:#e0e3e8!important}

/* ═══ BUTTONS ═══ */
button[kind="primary"],button[data-testid="stBaseButton-primary"]{
  background:linear-gradient(135deg,#448AFF,#7C4DFF)!important;border:none!important;
  border-radius:12px!important;font-weight:700!important;letter-spacing:.5px;
  padding:12px 32px!important;box-shadow:0 4px 20px rgba(68,138,255,.3)!important;
  transition:all .3s ease!important}
button[kind="primary"]:hover,button[data-testid="stBaseButton-primary"]:hover{
  transform:translateY(-2px)!important;box-shadow:0 8px 30px rgba(68,138,255,.4)!important}
button[kind="secondary"],button[data-testid="stBaseButton-secondary"]{
  background:rgba(20,27,61,.7)!important;border:1px solid rgba(100,120,255,.2)!important;
  border-radius:10px!important;color:#b0bec5!important}

/* ═══ RADIO NAV ═══ */
div[data-testid="stRadio"]>div{gap:4px}
div[data-testid="stRadio"] label{background:rgba(20,27,61,.5)!important;
  border:1px solid rgba(100,120,255,.1);border-radius:10px;padding:10px 14px!important;transition:all .25s}
div[data-testid="stRadio"] label:hover{border-color:rgba(100,120,255,.3);background:rgba(30,40,80,.7)!important}
div[data-testid="stRadio"] label[data-checked="true"]{
  border-color:rgba(68,138,255,.5)!important;background:rgba(68,138,255,.12)!important}

/* ═══ ALERTS / SUCCESS / WARNING / ERROR ═══ */
[data-testid="stAlert"],div[role="alert"],.stAlert,.stSuccess,.stWarning,.stError,.stInfo,
[data-testid="stNotification"]{
  background:rgba(20,27,61,.8)!important;border:1px solid rgba(100,120,255,.15)!important;
  border-radius:12px!important;color:#b0bec5!important}
.stSuccess,[data-baseweb="notification"][kind="positive"]{border-left:3px solid #00E676!important}
.stError,[data-baseweb="notification"][kind="negative"]{border-left:3px solid #FF5252!important}
.stWarning,[data-baseweb="notification"][kind="warning"]{border-left:3px solid #FFD740!important}

/* ═══ METRIC ═══ */
div[data-testid="stMetric"]{background:rgba(20,27,61,.6)!important;
  border:1px solid rgba(100,120,255,.1)!important;border-radius:12px!important;padding:16px!important}
div[data-testid="stMetric"] label{color:#546E7A!important;font-size:.7rem!important;
  text-transform:uppercase!important;letter-spacing:1.2px!important}
div[data-testid="stMetric"] [data-testid="stMetricValue"]{color:#e0e7ff!important;font-weight:800!important}

/* ═══ SPINNER ═══ */
.stSpinner>div{border-color:#448AFF transparent transparent!important}
[data-testid="stSpinner"]>div>span{color:#82B1FF!important}

/* ═══ CUSTOM CARDS ═══ */
.metric-card{background:linear-gradient(135deg,rgba(20,27,61,.85),rgba(30,40,80,.65))!important;
  backdrop-filter:blur(24px);border:1px solid rgba(100,120,255,.12);border-radius:16px;
  padding:20px 24px;text-align:center;position:relative;overflow:hidden;
  transition:all .35s cubic-bezier(.4,0,.2,1)}
.metric-card:hover{border-color:rgba(100,120,255,.3);box-shadow:0 8px 32px rgba(68,138,255,.12);transform:translateY(-2px)}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:16px 16px 0 0}
.metric-card.green::before{background:linear-gradient(90deg,#00E676,#69F0AE)}
.metric-card.blue::before{background:linear-gradient(90deg,#448AFF,#82B1FF)}
.metric-card.red::before{background:linear-gradient(90deg,#FF5252,#FF8A80)}
.metric-card.purple::before{background:linear-gradient(90deg,#CE93D8,#E1BEE7)}
.metric-card.amber::before{background:linear-gradient(90deg,#FFD740,#FFE57F)}
.metric-label{font-size:.78rem;color:#90A4AE!important;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;margin-bottom:6px}
.metric-value{font-size:2.1rem;font-weight:800;color:#ffffff!important;-webkit-text-fill-color:#ffffff!important;line-height:1.15}
.absa-result-card{background:rgba(20,27,61,.75);backdrop-filter:blur(20px);border-radius:16px;
  padding:28px 20px;text-align:center;border:2px solid rgba(100,120,255,.12);
  transition:all .4s cubic-bezier(.4,0,.2,1)}
.absa-result-card:hover{transform:translateY(-4px);box-shadow:0 16px 48px rgba(0,0,0,.4);
  border-color:rgba(100,120,255,.3)}
.absa-emoji{font-size:2.8rem;margin-bottom:10px}
.absa-aspect{font-size:.82rem;font-weight:700;letter-spacing:.8px;margin-bottom:8px;text-transform:uppercase}
.absa-sentiment{font-size:1.15rem;font-weight:800;letter-spacing:.5px}
.tag{display:inline-block;padding:5px 14px;border-radius:20px;font-size:.72rem;font-weight:600;letter-spacing:.5px}
.tag-green{background:rgba(0,230,118,.12);color:#69F0AE;border:1px solid rgba(0,230,118,.2)}
.tag-blue{background:rgba(68,138,255,.12);color:#82B1FF;border:1px solid rgba(68,138,255,.2)}
.tag-red{background:rgba(255,82,82,.12);color:#FF8A80;border:1px solid rgba(255,82,82,.2)}

/* ═══ SEPARATOR ═══ */
.stMarkdown hr{border-color:rgba(100,120,255,.08)!important;margin:24px 0!important}

/* ═══ TOOLTIP / POPOVER ═══ */
[data-testid="stTooltipContent"],[role="tooltip"],
[data-baseweb="tooltip"]>div,[data-baseweb="popover"]>div{
  background:#141b3d!important;border:1px solid rgba(100,120,255,.2)!important;
  color:#b0bec5!important;border-radius:10px!important}

/* ═══ IFRAME FIX (plotly) ═══ */
iframe{border:none!important;background:transparent!important}

/* ═══ HIDE STREAMLIT BRANDING ═══ */
#MainMenu{visibility:hidden}footer{visibility:hidden}
[data-testid="stToolbar"]{display:none!important}
</style>""", unsafe_allow_html=True)

def nss(s):
    s=pd.Series(s).dropna()
    if len(s)==0: return 0.0
    return ((s>0).sum()-(s<0).sum())/len(s)

@st.cache_data(ttl=600)
def load():
    if not DP.exists(): return None
    df=pd.read_parquet(DP)
    if "is_valid" in df.columns: df=df[df.is_valid==True].copy()
    for a in AC:
        if f"aspect_{a}" not in df.columns: df[f"aspect_{a}"]=False
        if f"aspect_{a}_sentiment" not in df.columns: df[f"aspect_{a}_sentiment"]=np.nan
    return df

def metric_html(label, value, cls="blue", icon=""):
    return f'<div class="metric-card {cls}"><div class="metric-label">{icon} {label}</div><div class="metric-value">{value}</div></div>'

def chart_layout(fig, h=400):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(20,27,61,.4)",
        font=dict(family="Inter",color="#ffffff",size=14),height=h,
        margin=dict(t=45,b=40,l=50,r=25),
        title_font=dict(size=16,color="#ffffff"),
        xaxis=dict(gridcolor="rgba(100,120,255,.1)",zerolinecolor="rgba(100,120,255,.15)",
                   tickfont=dict(color="#ffffff",size=12),title_font=dict(color="#ffffff",size=13)),
        yaxis=dict(gridcolor="rgba(100,120,255,.1)",zerolinecolor="rgba(100,120,255,.15)",
                   tickfont=dict(color="#ffffff",size=12),title_font=dict(color="#ffffff",size=13)),
        legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(size=13,color="#ffffff")))
    return fig

def sidebar(df):
    st.sidebar.markdown('<div style="text-align:center;padding:16px 0"><span style="font-size:2.5rem">⚡</span><br><span style="font-size:1.1rem;font-weight:800;background:linear-gradient(135deg,#00E676,#448AFF);-webkit-background-clip:text;-webkit-text-fill-color:transparent">EV Sentiment</span><br><span style="font-size:.7rem;color:#546E7A;letter-spacing:2px">ABSA DASHBOARD v5.2</span></div>', unsafe_allow_html=True)
    st.sidebar.markdown("---")
    brands=sorted(df.brand_target.unique().tolist())
    sb=st.sidebar.multiselect("🏷️ Brands",brands,default=[b for b in ["VinFast","BYD"] if b in brands])
    an=list(AL.values()); ak=list(AL.keys())
    sal=st.sidebar.multiselect("📊 Aspects",an,default=an)
    sa=[k for k,v in AL.items() if v in sal]
    pl=sorted(df.platform_source.unique().tolist())
    sp=st.sidebar.multiselect("📡 Sources",pl,default=pl)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f'<div style="text-align:center"><div class="tag tag-blue">PhoBERT ABSA</div></div>',unsafe_allow_html=True)
    return sb or ["VinFast","BYD"], sa or ak, sp or pl

def page_overview(df,brands,aspects,platforms):
    st.title("Executive Overview")
    fdf=df[df.brand_target.isin(brands)&df.platform_source.isin(platforms)]
    pos_p=(fdf.sentiment==1).mean()*100 if "sentiment" in fdf.columns else 0
    neg_p=(fdf.sentiment==-1).mean()*100 if "sentiment" in fdf.columns else 0
    n=nss(fdf.get("sentiment",pd.Series()))
    eng=fdf.engagement_score.sum() if "engagement_score" in fdf.columns else 0
    c1,c2,c3,c4,c5=st.columns(5)
    with c1: st.markdown(metric_html("Total Records",f"{len(fdf):,}","blue","📝"),unsafe_allow_html=True)
    with c2: st.markdown(metric_html("Positive",f"{pos_p:.1f}%","green","🟢"),unsafe_allow_html=True)
    with c3: st.markdown(metric_html("Negative",f"{neg_p:.1f}%","red","🔴"),unsafe_allow_html=True)
    with c4: st.markdown(metric_html("Overall NSS",f"{n:+.3f}","purple","📈"),unsafe_allow_html=True)
    with c5: st.markdown(metric_html("Engagements",f"{eng:,}","amber","❤️"),unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1:
        st.markdown("## 🏷️ Brand Distribution")
        bc=fdf.brand_target.value_counts()
        fig=px.pie(values=bc.values,names=bc.index,color=bc.index,color_discrete_map=BC,hole=.5)
        fig.update_traces(textinfo="percent+label",textfont_size=12,marker=dict(line=dict(color='rgba(10,14,39,1)',width=2)))
        st.plotly_chart(chart_layout(fig,380),use_container_width=True)
    with c2:
        st.markdown("## 💬 Sentiment by Brand")
        if "sentiment" in fdf.columns:
            sb_data=[]
            for b in brands:
                bdf=fdf[fdf.brand_target==b]
                sb_data.append({"Brand":b,"Positive":(bdf.sentiment==1).sum(),"Neutral":(bdf.sentiment==0).sum(),"Negative":(bdf.sentiment==-1).sum()})
            sbd=pd.DataFrame(sb_data)
            fig=go.Figure()
            for s,c in SC.items():
                if s in sbd.columns: fig.add_trace(go.Bar(name=s,x=sbd.Brand,y=sbd[s],marker_color=c,marker_line=dict(width=0)))
            fig.update_layout(barmode="stack")
            st.plotly_chart(chart_layout(fig,380),use_container_width=True)
    st.markdown("## 📈 Net Sentiment Score by Brand")
    if "sentiment" in fdf.columns:
        nd=[{"Brand":b,"NSS":nss(fdf[fdf.brand_target==b].sentiment),"Count":len(fdf[fdf.brand_target==b])} for b in brands if len(fdf[fdf.brand_target==b])>0]
        if nd:
            ndf=pd.DataFrame(nd)
            fig=px.bar(ndf,x="Brand",y="NSS",color="Brand",color_discrete_map=BC,text_auto=".3f")
            fig.update_traces(textposition="outside",marker_line_width=0)
            fig.update_yaxes(range=[-1,1])
            st.plotly_chart(chart_layout(fig,350),use_container_width=True)

def page_absa(df,brands,aspects,platforms):
    st.title("Aspect-Based Sentiment Analysis")
    st.markdown('<div class="tag tag-blue" style="margin-bottom:20px">Each aspect analyzed with its OWN sentiment — not a global label</div>',unsafe_allow_html=True)
    fdf=df[df.brand_target.isin(brands)&df.platform_source.isin(platforms)]
    st.markdown("## 🗺️ Aspect × Brand Heatmap")
    hd=[]
    for a in aspects:
        ac_col,as_col=f"aspect_{a}",f"aspect_{a}_sentiment"
        for b in brands:
            m=(fdf.brand_target==b)
            if ac_col in fdf.columns: m=m&(fdf[ac_col]==True)
            bd=fdf[m]
            if as_col in bd.columns and bd[as_col].notna().sum()>0:
                n=nss(bd[as_col]); cnt=int(bd[as_col].notna().sum())
            else:
                n=nss(bd.get("sentiment",pd.Series())); cnt=len(bd)
            hd.append({"Aspect":AL.get(a,a),"Brand":b,"NSS":n,"Count":cnt})
    if hd:
        hdf=pd.DataFrame(hd); pv=hdf.pivot(index="Aspect",columns="Brand",values="NSS").fillna(0)
        pc=hdf.pivot(index="Aspect",columns="Brand",values="Count").fillna(0)
        txt=[[f"{pv.iloc[i,j]:+.3f}<br><span style='font-size:10px;color:#78909C'>n={int(pc.iloc[i,j])}</span>" for j in range(len(pv.columns))] for i in range(len(pv.index))]
        fig=go.Figure(go.Heatmap(z=pv.values,x=pv.columns,y=pv.index,text=txt,texttemplate="%{text}",
            colorscale=[[0,"#FF5252"],[.35,"#FF8A80"],[.5,"#37474F"],[.65,"#69F0AE"],[1,"#00E676"]],
            zmid=0,zmin=-1,zmax=1,colorbar=dict(title="NSS",tickvals=[-1,-.5,0,.5,1],len=.8),
            xgap=3,ygap=3))
        fig.update_layout(height=max(300,len(aspects)*65+80))
        st.plotly_chart(chart_layout(fig,max(300,len(aspects)*65+80)),use_container_width=True)
    st.markdown("## 📊 Sentiment per Aspect")
    cols=st.columns(min(len(aspects),3))
    for i,a in enumerate(aspects):
        with cols[i%len(cols)]:
            ac_col,as_col=f"aspect_{a}",f"aspect_{a}_sentiment"
            m=fdf[ac_col]==True if ac_col in fdf.columns else pd.Series([False]*len(fdf))
            sub=fdf[m]
            if as_col in sub.columns and sub[as_col].notna().sum()>0:
                sc_=sub[as_col].map(SM).value_counts()
            elif "sentiment" in sub.columns:
                sc_=sub.sentiment.map(SM).value_counts()
            else: st.info("No data"); continue
            fig=px.pie(values=sc_.values,names=sc_.index,color=sc_.index,color_discrete_map=SC,hole=.55)
            fig.update_traces(textinfo="percent+label",textfont_size=13,marker=dict(line=dict(color='rgba(10,14,39,1)',width=2)))
            fig.update_layout(title=dict(text=AL.get(a,a),font=dict(size=14,color="#ffffff")),showlegend=False)
            st.plotly_chart(chart_layout(fig,240),use_container_width=True)
            n_val=nss(sub.get(as_col,sub.get("sentiment",pd.Series())))
            color="#00E676" if n_val>0 else "#FF5252" if n_val<0 else "#90A4AE"
            st.markdown(f'<div style="text-align:center;padding:8px 0"><span style="font-size:1.6rem;font-weight:900;color:{color}">{n_val:+.3f}</span><br><span style="font-size:.85rem;color:#90A4AE;font-weight:500">{int(m.sum())} mentions</span></div>',unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("## 💬 Verbatim Explorer")
    c1,c2=st.columns(2)
    with c1: sel_a=st.selectbox("Aspect",[AL[a] for a in aspects])
    with c2: sel_s=st.selectbox("Sentiment",["Positive","Negative","Neutral"])
    ak=[k for k,v in AL.items() if v==sel_a][0]
    sv={"Positive":1,"Negative":-1,"Neutral":0}[sel_s]
    m=fdf.get(f"aspect_{ak}",pd.Series([False]*len(fdf)))==True
    sub=fdf[m]
    as_col=f"aspect_{ak}_sentiment"
    q=sub[sub[as_col]==sv] if as_col in sub.columns else sub[sub.get("sentiment",pd.Series())==sv]
    if len(q)>0:
        dc=[c for c in ["brand_target","raw_text","platform_source"] if c in q.columns]
        display_df=q[dc].head(20).rename(columns={"brand_target":"Brand","raw_text":"Comment","platform_source":"Source"})
        # Render as HTML table for guaranteed dark theme compatibility
        rows_html=""
        for _,row in display_df.iterrows():
            cells="".join(f'<td style="padding:10px 14px;border-bottom:1px solid rgba(100,120,255,.08);color:#e0e3e8;font-size:.88rem;max-width:600px;word-wrap:break-word">{row[c]}</td>' for c in display_df.columns)
            rows_html+=f'<tr style="transition:background .2s" onmouseover="this.style.background=\'rgba(68,138,255,.08)\'" onmouseout="this.style.background=\'transparent\'">{cells}</tr>'
        headers="".join(f'<th style="padding:10px 14px;text-align:left;color:#82B1FF;font-weight:700;font-size:.8rem;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid rgba(100,120,255,.2);background:rgba(20,27,61,.8)">{c}</th>' for c in display_df.columns)
        st.markdown(f'''
        <div style="border:1px solid rgba(100,120,255,.15);border-radius:12px;overflow:hidden;max-height:420px;overflow-y:auto">
        <table style="width:100%;border-collapse:collapse;background:rgba(15,21,53,.9)">
        <thead><tr>{headers}</tr></thead>
        <tbody>{rows_html}</tbody>
        </table></div>''',unsafe_allow_html=True)
        st.markdown(f'<div style="margin-top:12px" class="tag tag-{"green" if sel_s=="Positive" else "red" if sel_s=="Negative" else "blue"}">Showing 20 of {len(q)} {sel_s.lower()} quotes for {sel_a}</div>',unsafe_allow_html=True)
    else: st.info(f"No {sel_s.lower()} quotes for {sel_a}")

def page_demo():
    st.title("Live ABSA Demo")
    st.markdown('<div class="tag tag-blue" style="margin-bottom:16px">Real-time aspect-based sentiment analysis powered by PhoBERT</div>',unsafe_allow_html=True)
    txt=st.text_area("Enter Vietnamese EV comment:",value="Pin VinFast VF8 rất tốt, sạc nhanh nhưng dịch vụ hậu mãi quá tệ. Giá hơi đắt so với BYD Dolphin.",height=120)
    if st.button("⚡ Analyze Sentiment",type="primary",use_container_width=True):
        with st.spinner("🔬 Analyzing..."):
            try:
                sys.path.insert(0,str(Path(__file__).parent))
                from src.nlp.absa import AspectSentimentAnalyzer
                from src.config import ASPECT_MAP,POSITIVE_LEXICON,NEGATIVE_LEXICON,NEGATION_PARTICLES
                az=AspectSentimentAnalyzer(ASPECT_MAP,POSITIVE_LEXICON,NEGATIVE_LEXICON,NEGATION_PARTICLES)
                tl=txt.lower().replace("_"," ").split()
                det=[a for a,kws in ASPECT_MAP.items() if any(kw in t for t in tl for kw in kws)]
                res=az.analyze(txt,det)
                st.success(f"✅ Analyzed with **{az.mode}** · {len(det)} aspects detected")
                if res:
                    cols=st.columns(len(res))
                    for i,(a,s) in enumerate(res.items()):
                        sl=SM.get(s,"?"); clr=SC.get(sl,"#78909C")
                        emo={"Positive":"✅","Negative":"❌","Neutral":"➖"}.get(sl,"❓")
                        with cols[i]:
                            st.markdown(f'<div class="absa-result-card" style="border-color:{clr}40"><div class="absa-emoji">{emo}</div><div class="absa-aspect" style="color:#b0bec5">{AL.get(a,a)}</div><div class="absa-sentiment" style="color:{clr}">{sl}</div></div>',unsafe_allow_html=True)
                else: st.warning("No aspects detected.")
            except Exception as e: st.error(f"Error: {e}")

def page_model(df,brands):
    st.title("Model Performance")
    fdf=df[df.brand_target.isin(brands)]
    if "sentiment" not in fdf.columns: st.warning("No data"); return
    c1,c2=st.columns(2)
    with c1:
        st.markdown("## 📊 Sentiment Distribution")
        sc_=fdf.sentiment.map(SM).value_counts()
        fig=px.bar(x=sc_.index,y=sc_.values,color=sc_.index,color_discrete_map=SC,text_auto=True)
        fig.update_traces(marker_line_width=0)
        fig.update_layout(showlegend=False,xaxis_title="",yaxis_title="Count")
        st.plotly_chart(chart_layout(fig,350),use_container_width=True)
    with c2:
        st.markdown("## 🔬 Aspect Coverage")
        cd=[{"Aspect":AL[a],"Count":int(fdf[f"aspect_{a}"].sum()),"Coverage":fdf[f"aspect_{a}"].mean()*100,"Color":AC[a]} for a in AL if f"aspect_{a}" in fdf.columns]
        if cd:
            cdf=pd.DataFrame(cd)
            fig=px.bar(cdf,x="Coverage",y="Aspect",orientation="h",color="Aspect",color_discrete_sequence=[d["Color"] for d in cd],text="Count")
            fig.update_traces(marker_line_width=0,textposition="outside")
            fig.update_layout(showlegend=False,xaxis_title="Coverage %",yaxis_title="")
            st.plotly_chart(chart_layout(fig,350),use_container_width=True)
    st.markdown("---")
    st.markdown("## ℹ️ Pipeline Info")
    c1,c2,c3=st.columns(3)
    has_absa=any(f"aspect_{a}_sentiment" in fdf.columns and fdf[f"aspect_{a}_sentiment"].notna().any() for a in AL)
    with c1: st.markdown(metric_html("ABSA Engine","PhoBERT" if has_absa else "Rule-Based","blue","🧠"),unsafe_allow_html=True)
    with c2: st.markdown(metric_html("Aspects",str(len(AL)),"green","📊"),unsafe_allow_html=True)
    tot=sum(fdf[f"aspect_{a}_sentiment"].notna().sum() for a in AL if f"aspect_{a}_sentiment" in fdf.columns)
    with c3: st.markdown(metric_html("ABSA Labels",f"{int(tot):,}","purple","🏷️"),unsafe_allow_html=True)

def main():
    df=load()
    if df is None:
        st.error("⚠️ No data. Run pipeline first."); page_demo(); return
    brands,aspects,platforms=sidebar(df)
    st.sidebar.markdown("---")
    page=st.sidebar.radio("📄 Navigation",["📊 Overview","🔬 ABSA Explorer","📈 Analytics (21 Charts)","⚡ Live Demo","🤖 Model"])
    if page.startswith("📊"): page_overview(df,brands,aspects,platforms)
    elif page.startswith("🔬"): page_absa(df,brands,aspects,platforms)
    elif page.startswith("📈"):
        from pages_analytics import render_analytics_page
        render_analytics_page(df,brands,aspects,platforms)
    elif page.startswith("⚡"): page_demo()
    else: page_model(df,brands)
    st.sidebar.markdown('<div style="text-align:center;padding:16px 0;margin-top:24px;border-top:1px solid rgba(100,120,255,.1)"><span style="font-size:.65rem;color:#37474F;letter-spacing:1px">EV SENTIMENT v5.2<br>PhoBERT ABSA<br>© 2026</span></div>',unsafe_allow_html=True)

if __name__=="__main__": main()
