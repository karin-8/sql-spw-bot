import os
import streamlit as st
import yaml
from modules.config_manager import load_config, save_config, AppConfig, AIConfig, DataConfig, Snippet
from modules import sql_engine

st.set_page_config(page_title="Config • SQL Chat", page_icon="⚙️", layout="wide")
st.title("⚙️ Config")

if "app_config" not in st.session_state:
    st.session_state.app_config = load_config()
cfg: AppConfig = st.session_state.app_config

st.subheader("AI Settings")
c1, c2, c3 = st.columns([1,1,1])
with c1:
    provider = st.selectbox("Provider", ["openai"], index=0)
with c2:
    model = st.text_input("Model", value=cfg.ai.model, help="e.g., gpt-4o-mini")
with c3:
    temperature = st.slider("Temperature", 0.0, 1.0, value=float(cfg.ai.temperature), step=0.1)

offline = st.toggle("Offline Demo Mode (no API calls)", value=cfg.ai.offline_demo_mode, help="Use a simple rule-based SQL generator and answerer.")

sys_prompt = st.text_area("System Prompt (Answering)", value=cfg.ai.system_prompt, height=140)
sql_prompt = st.text_area("SQL Synthesizer Prompt", value=cfg.ai.sql_synth_prompt, height=160)

st.divider()
st.subheader("Data Settings")
d1, d2 = st.columns([2,1])
with d1:
    file_path = st.text_input("Data file path (.csv or .xlsx)", value=cfg.data.file_path)
with d2:
    table_name = st.text_input("Table name", value=cfg.data.table_name)

details = st.text_area("Additional details (for the model)", value=cfg.data.additional_details, height=130)

build = st.button("Rebuild In-Memory Table")
if build:
    try:
        eng = sql_engine.build_engine_from_file(file_path, table_name)
        st.session_state.engine = eng
        st.session_state.engine_src = (file_path, table_name)
        st.success("Rebuilt table successfully.")
    except Exception as e:
        st.error(f"Failed: {e}")

with st.expander("Preview Schema"):
    if "engine" in st.session_state:
        st.code(st.session_state.engine.schema_text(), language="sql")
    else:
        st.info("No engine yet — open Chat once or click Rebuild.")

st.divider()
st.subheader("SQL Snippet Library (optional hints)")

# --- initialize working list in session_state ---
if "snips" not in st.session_state:
    # make a shallow copy of dataclass instances; adjust if you need deep copy
    st.session_state.snips = [Snippet(name=s.name, sql=s.sql) for s in cfg.snippets]

snips = st.session_state.snips  # alias for brevity

# --- existing items (editable + deletable) ---
delete_indices = []
for i, s in enumerate(snips):
    with st.container(border=True):
        n = st.text_input(f"Name #{i+1}", value=s.name, key=f"sn-name-{i}")
        q = st.text_area(f"SQL #{i+1}", value=s.sql, key=f"sn-sql-{i}", height=80)
        if st.button(f"Delete #{i+1}", key=f"sn-del-{i}"):
            delete_indices.append(i)
        else:
            # write edits back into the working list
            snips[i] = Snippet(name=n, sql=q)

# apply deletions after the loop to avoid index shifts
for idx in sorted(delete_indices, reverse=True):
    snips.pop(idx)
    # also clean up any orphaned widget state for neatness
    st.session_state.pop(f"sn-name-{idx}", None)
    st.session_state.pop(f"sn-sql-{idx}", None)

# --- add new snippet (works across reruns) ---
with st.container(border=True):
    st.markdown("**Add a snippet**")
    newn = st.text_input("New snippet name", key="new-sn-n")
    news = st.text_area("New snippet SQL", key="new-sn-s", height=60)
    if st.button("Add snippet"):
        if newn and news:
            snips.append(Snippet(name=newn, sql=news))
            # clear inputs so the user sees that it was added
            st.session_state["new-sn-n"] = ""
            st.session_state["new-sn-s"] = ""
            st.success("Snippet added to the working list. Click 'Save All' to persist.")
        else:
            st.warning("Provide both name and SQL.")


st.divider()
st.subheader("Secrets")
api_key = st.text_input("OPENAI_API_KEY", type="password", help="If set here, it will be exported to the process for this session.")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    st.success("OPENAI_API_KEY set for this process.")

st.divider()
if st.button("Save All"):
    cfg.ai.provider = provider
    cfg.ai.model = model
    cfg.ai.temperature = float(temperature)
    cfg.ai.offline_demo_mode = bool(offline)
    cfg.ai.system_prompt = sys_prompt
    cfg.ai.sql_synth_prompt = sql_prompt
    cfg.data.file_path = file_path
    cfg.data.table_name = table_name
    cfg.data.additional_details = details

    # persist from working copy
    cfg.snippets = st.session_state.snips
    save_config(cfg)
    st.success("Saved config.yaml")

