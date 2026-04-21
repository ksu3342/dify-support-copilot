from app.ingest.clean import extract_title_and_clean_text


def test_extract_title_and_clean_text_removes_noise_and_normalizes_whitespace():
    html = """
    <html>
      <head>
        <title>  Dify   Docker Compose  </title>
        <style>.hidden { display:none; }</style>
        <script>console.log('noise')</script>
      </head>
      <body>
        <nav>Navigation links</nav>
        <main>
          <h1>Install Dify</h1>
          <p>Use   Docker Compose   for local setup.</p>
          <div aria-hidden="true">Ignore me</div>
        </main>
        <footer>Footer noise</footer>
      </body>
    </html>
    """

    title, cleaned_text = extract_title_and_clean_text(html)

    assert title == "Dify Docker Compose"
    assert "Navigation links" not in cleaned_text
    assert "Footer noise" not in cleaned_text
    assert "console.log" not in cleaned_text
    assert "Ignore me" not in cleaned_text
    assert "Install Dify" in cleaned_text
    assert "Use Docker Compose for local setup." in cleaned_text


def test_extract_title_and_clean_text_prefers_dify_content_area_and_preserves_real_page_text():
    html = """
    <html>
      <head>
        <title>Dify Docs | API</title>
      </head>
      <body>
        <nav>
          Get Started
          Plugins
          Tools
          Workspace
        </nav>
        <div id="content-area">
          <header>
            <div class="eyebrow">Publish</div>
            <div>
              <h1 id="page-title">API</h1>
              <div id="page-context-menu">Copy page</div>
            </div>
            <div class="text-lg">
              <p>Integrate your Dify workflows anywhere</p>
            </div>
          </header>
          <div id="content" class="mdx-content prose">
            <p>\u200b</p>
            <h2>Getting Started</h2>
            <p>You can use your Dify app as a backend API service out-of-box.</p>
          </div>
          <div class="feedback-toolbar">Was this page helpful?</div>
          <div id="pagination">Previous Overview Next</div>
        </div>
        <aside>
          Overview
          Billing
        </aside>
        <footer>Footer noise</footer>
      </body>
    </html>
    """

    title, cleaned_text = extract_title_and_clean_text(html)

    assert title == "Dify Docs | API"
    assert cleaned_text.startswith("API")
    assert "Integrate your Dify workflows anywhere" in cleaned_text
    assert "Getting Started" in cleaned_text
    assert "You can use your Dify app as a backend API service out-of-box." in cleaned_text
    assert "Get Started" not in cleaned_text
    assert "Plugins" not in cleaned_text
    assert "Tools" not in cleaned_text
    assert "Workspace" not in cleaned_text
    assert "Billing" not in cleaned_text
    assert "Copy page" not in cleaned_text
    assert "Was this page helpful?" not in cleaned_text
    assert "Previous Overview Next" not in cleaned_text
