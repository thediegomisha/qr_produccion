import streamlit as st


def apply_main_theme() -> None:
    st.markdown(
        """
        <style>
          :root {
            --brand-blue-1: #0b3a8f;
            --brand-blue-2: #1f6fd9;
            --brand-cyan: #1b9ccf;
            --brand-green: #2e7d32;
          }

          .stApp {
            background: radial-gradient(circle at 12% 12%, #e7f2ff 0%, #f6fbff 35%, #f4faf6 100%);
          }

          section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b3a8f 0%, #1f6fd9 60%, #1b9ccf 100%);
          }

          section[data-testid="stSidebar"] * {
            color: #eef6ff;
          }

          section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: #eef6ff;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label {
            border: 1px solid rgba(255, 255, 255, 0.28);
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.08);
            margin-bottom: 0.32rem;
            min-height: 2.4rem;
            padding: 0.3rem 0.45rem;
            transition: background-color 0.2s ease, transform 0.12s ease, border-color 0.2s ease;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p {
            margin: 0;
            font-size: 0.92rem !important;
            font-weight: 600;
            line-height: 1.25;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
            background: rgba(255, 255, 255, 0.2);
            border-color: rgba(255, 255, 255, 0.55);
            transform: translateX(2px);
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
            background: rgba(255, 255, 255, 0.28);
            border-color: rgba(255, 255, 255, 0.8);
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.35);
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked):hover {
            transform: none;
          }

          .user-panel {
            background: linear-gradient(135deg, rgba(6, 28, 73, 0.55), rgba(26, 104, 198, 0.55));
            border-radius: 14px;
            color: #ffffff;
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 25px rgba(4, 23, 61, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.25);
          }

          .user-panel .user-label {
            font-size: 0.78rem;
            opacity: 0.85;
            letter-spacing: 0.03em;
          }

          .user-panel .user-name {
            font-size: 1.02rem;
            font-weight: 700;
            margin-top: 0.1rem;
          }

          .user-panel .user-role {
            font-size: 0.85rem;
            opacity: 0.95;
          }

          .app-version {
            text-align: center;
            font-size: 0.9rem;
            font-weight: 700;
            opacity: 0.98;
            margin-bottom: 0.35rem;
          }

          button[kind="primary"] {
            background: linear-gradient(135deg, var(--brand-blue-2), var(--brand-cyan)) !important;
            border: none !important;
          }

          button[kind="primary"]:hover {
            filter: brightness(1.05);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_login_theme() -> None:
    st.markdown(
        """
        <style>
          .login-overlay{
            position: fixed; inset: 0;
            background: linear-gradient(135deg,#0b3a8f 0%,#1f6fd9 65%,#1b9ccf 100%);
            z-index:-1;
          }

          div[data-testid="stContainer"]{
            background:#ffffff;
            padding: 1.8rem 1.6rem 1.4rem 1.6rem;
            border-radius: 20px;
            box-shadow: 0 24px 44px rgba(8, 44, 104, 0.35);
            border-top: 6px solid #1F6FD9;
          }

          .login-title{
            text-align:center;
            font-size:1.65rem;
            font-weight:700;
            color:#0b3a8f;
            margin: 0.2rem 0 0.2rem 0;
          }
          .login-subtitle{
            text-align:center;
            color:#4b5e86;
            font-size:0.9rem;
            margin: 0 0 1.0rem 0;
          }

          .stTextInput input{
            background-color:#f2f7ff !important;
            border-radius:10px !important;
            border:1px solid #c8dfff !important;
          }
          .stTextInput input:focus{
            border-color:#1F6FD9 !important;
            box-shadow:0 0 0 1px #1F6FD9 !important;
          }

          div[data-testid="stFormSubmitButton"] > button{
            width:100%;
            background: linear-gradient(135deg,#1F6FD9,#0B3A8F) !important;
            color:white !important;
            font-weight:600 !important;
            padding:0.65rem !important;
            border-radius:12px !important;
            border:none !important;
            margin-top:0.4rem !important;
          }

          div[data-testid="stTextInput"] button{
            width:auto !important;
            padding:0.25rem 0.5rem !important;
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
          }
        </style>
        <div class="login-overlay"></div>
        """,
        unsafe_allow_html=True,
    )
