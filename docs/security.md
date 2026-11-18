# LightMq Security Architecture

## 1. Security Principles

LightMq is architected to protect user privacy and system security while running web content:

1. **Chromium Process Isolation**: Web page rendering runs inside Chromium's isolated worker processes, sandboxed from the host operating system.
2. **Profile Boundary Separation**: Data from normal profiles (cookies, local storage, cache) is strictly isolated from Incognito / private browsing profiles.
3. **URL & Scheme Sanitization**: All incoming navigation requests are parsed and validated against strict scheme allowlists before being passed to WebEngine.
4. **Certificate Verification**: All TLS/SSL connections are validated against the system trust store; untrusted or expired certificates require explicit user override.
5. **Granular Origin-Based Permissions**: Hardware and sensitive capabilities (camera, microphone, geolocation, desktop notifications) require explicit per-origin user approval.

---

## 2. Security Subsystems & Components

### URL Validator (`src/browser/security/url_validator.py`)
- Restricts navigations to safe schemes: `http://`, `https://`, `file://` (explicitly allowed local files), and internal browser pages (`about:blank`, `lightmq://*`).
- Rejects dangerous schemes (`javascript:`, `vbscript:`, `data:` for top-level navigation).
- Sanitizes user input before passing to `QUrl`.

### Certificate Handler (`src/browser/security/certificate_handler.py`)
- Intercepts `QWebEnginePage.certificateError`.
- Evaluates the nature of the error (expired, self-signed, host mismatch).
- Presents a standard security interstitial dialog warning users of potential MitM attacks.
- Prevents silent bypass of security warnings.

### Permission Policy Subsystem (`src/browser/security/permission_policy.py`)
- Implements `QWebEnginePage.featurePermissionRequested`.
- Maps features:
  - `Geolocation`
  - `MediaAudioCapture` (Microphone)
  - `MediaVideoCapture` (Webcam)
  - `Notifications`
  - `DesktopVideoCapture` (Screen share)
- Stores persistent user decisions in the local settings repository indexed by origin URL (`scheme://domain:port`).

### Request Interceptor (`src/browser/webengine/request_interceptor.py`)
- Subclasses `QWebEngineUrlRequestInterceptor`.
- Inspects all outgoing HTTP/HTTPS web requests before network transmission.
- Enables:
  - Anti-tracking header injection (`DNT: 1`, `Sec-GPC: 1`).
  - Request blocking for known advertising, tracking, and malware domains.
  - Blocking unauthorized mixed content (HTTP resources loaded on HTTPS pages).

### Private Browsing Isolation (`src/browser/features/private_browsing/`)
- Uses off-the-record `QWebEngineProfile` instances.
- All cookies, cache, web storage, and session data remain strictly in memory and are discarded immediately upon closing the private window or session.
