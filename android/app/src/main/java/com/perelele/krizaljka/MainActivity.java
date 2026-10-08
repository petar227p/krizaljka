package com.perelele.krizaljka;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;

/**
 * Shows the crossword player (index.html) from the app's assets.
 * The puzzles and pictures are copied into assets at build time by build.sh.
 */
public class MainActivity extends Activity {

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WebView webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);   // the player is plain JavaScript
        settings.setDomStorageEnabled(true);   // saves progress and difficulty per device
        settings.setAllowFileAccess(true);
        settings.setSupportZoom(true);           // pinch-zoom: zooming in shows the clue text in the squares
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);  // no on-screen +/- buttons

        webView.loadUrl("file:///android_asset/index.html");
        setContentView(webView);
    }
}
