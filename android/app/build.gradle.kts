plugins {
    id("com.android.application")
}

android {
    namespace = "com.perelele.krizaljka"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.perelele.krizaljka"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
