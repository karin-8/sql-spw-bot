import streamlit as st

def inject():
    st.markdown(
        """
        <style>
        .chat-container { max-width: 900px; margin: 0 auto; }
        .stChatMessageContent { font-size: 0.98rem; }
        .assistant-bubble {
            background: #f5f7fb;
            border: 1px solid #e6eaf2;
            padding: 12px 14px;
            border-radius: 16px;
        }
        .user-bubble {
            background: #eef7ff;
            border: 1px solid #d3ecff;
            padding: 12px 14px;
            border-radius: 16px;
        }
        .codebox {
            background: #0e1117;
            color: #e6edf3;
            padding: 10px 12px;
            border-radius: 10px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            font-size: 0.9rem;
            overflow-x: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
