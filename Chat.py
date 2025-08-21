import os
import streamlit as st
from modules.ui_css import inject
from modules.config_manager import load_config, save_config
from modules import sql_engine
from modules.ai_agent import synthesize_sql, answer_with_data, pick_most_related

st.set_page_config(page_title="SQL Chat", page_icon="💬", layout="wide")

inject()
st.title("💬 SQL Chat")
st.caption("LangChain-powered demo. Data from a local CSV/Excel simulated as a SQL table.")

# Load config
if "app_config" not in st.session_state:
    st.session_state.app_config = load_config()
cfg = st.session_state.app_config

# Build or rebuild engine if needed
if "engine" not in st.session_state or st.session_state.get("engine_src") != (cfg.data.file_path, cfg.data.table_name):
    try:
        eng = sql_engine.build_engine_from_file(cfg.data.file_path, cfg.data.table_name)
        st.session_state.engine = eng
        st.session_state.engine_src = (cfg.data.file_path, cfg.data.table_name)
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.stop()

engine = st.session_state.engine

# sidebar status & controls
with st.sidebar:
    st.subheader("Run Mode")
    offline = cfg.ai.offline_demo_mode
    if offline:
        st.info("Offline Demo Mode is ON (rule-based). Turn it off in Config to use your model/API key.")
    else:
        st.success(f"Using provider={cfg.ai.provider}, model={cfg.ai.model}")
    st.markdown("---")
    st.markdown("**Table:** `" + cfg.data.table_name + "`")
    with st.expander("Schema (auto-inferred)"):
        st.code(engine.schema_text(), language="sql")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_input = st.chat_input("Ask about your data… (e.g., top 3 items by revenue)")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Agent: pick most-related SQL from snippets
    candidate_sql = pick_most_related(user_input, [{"name": s.name, "sql": s.sql} for s in cfg.snippets])

    # Compose inputs for SQL synthesis
    schema = engine.schema_text()
    details = cfg.data.additional_details

    # Call AI (or offline) to synthesize SQL
    sql_query = synthesize_sql(
        cfg={
            "ai": {
                "provider": cfg.ai.provider,
                "model": cfg.ai.model,
                "temperature": cfg.ai.temperature,
                "offline_demo_mode": cfg.ai.offline_demo_mode,
                "system_prompt": cfg.ai.system_prompt,
                "sql_synth_prompt": cfg.ai.sql_synth_prompt,
            }
        },
        user_query=user_input,
        schema=schema,
        details=details,
        candidate_sql=candidate_sql,
        table_name=cfg.data.table_name,
    )

    # Run SQL
    try:
        cols, rows = engine.execute_safe_select(sql_query)
    except Exception as e:
        cols, rows = [], []
        error_text = f"SQL failed: {e}"
    else:
        error_text = None

    # Show assistant message
    with st.chat_message("assistant"):
        st.markdown("**SQL used:**")
        st.code(sql_query, language="sql")
        if error_text:
            st.error(error_text)
        else:
            st.markdown("**Data preview:**")
            st.dataframe(rows, use_container_width=True, hide_index=True)

        # Ask LLM (or fallback) to narrate
        try:
            answer = answer_with_data(
                cfg={
                    "ai": {
                        "provider": cfg.ai.provider,
                        "model": cfg.ai.model,
                        "temperature": cfg.ai.temperature,
                        "offline_demo_mode": cfg.ai.offline_demo_mode,
                        "system_prompt": cfg.ai.system_prompt,
                        "sql_synth_prompt": cfg.ai.sql_synth_prompt,
                    }
                },
                user_query=user_input,
                sql=sql_query,
                columns=cols,
                rows=rows,
            )
        except Exception as e:
            answer = f"(Answer generator failed: {e})"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
