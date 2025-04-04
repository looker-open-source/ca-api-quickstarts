import streamlit as st

def show_login_button():
    """Display login button"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style='text-align: center; padding: 20px;'>
                <h2>Welcome</h2>
                <p>Please sign in to continue</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        return st.button("Sign in with Google", type="primary", use_container_width=True)

def show_user_profile(user_info):
    """Display user profile"""
    st.sidebar.image(user_info.get('picture', ''), width=100)
    st.sidebar.write(f"Welcome, {user_info.get('name', 'User')}!")
    if st.sidebar.button("Logout"):
        return True
    return False
