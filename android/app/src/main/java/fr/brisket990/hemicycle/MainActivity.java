package fr.brisket990.hemicycle;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private static final String SITE = "https://brisket990.github.io/hemicycle/";
    private WebView web;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (u.toString().startsWith(SITE)) return false;
                // Liens vers l'Assemblée et autres sites : navigateur
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) {}
                return true;
            }
            @Override
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    v.loadDataWithBaseURL(null,
                        "<html><body style='font-family:sans-serif;background:#12151c;color:#e7eaf0;padding:32px'>"
                        + "<h2>Pas de connexion</h2><p>Le site des votes n'a pas pu être chargé. "
                        + "Vérifiez votre connexion puis <a style='color:#8aa7ff' href='" + SITE + "'>réessayez</a>.</p></body></html>",
                        "text/html", "utf-8", null);
                }
            }
        });
        if (state != null) web.restoreState(state); else web.loadUrl(SITE);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
}
