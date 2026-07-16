---
title: "Shipping Flutter Desktop Apps"
slug: "flutter-desktop-windows-macos-linux"
description: "Release Flutter desktop apps on Windows, macOS, and Linux: platform channels, window management, installers, code signing, and the desktop-specific bugs mobile devs miss."
datePublished: "2024-10-22"
dateModified: "2024-10-22"
tags: ["Flutter", "Dart"]
keywords: "Flutter desktop, Flutter Windows, Flutter macOS, Flutter Linux, desktop app release, window_manager Flutter"
faq:
  - q: "Is Flutter ready for production desktop apps?"
    a: "Flutter desktop reached stable for Windows, macOS, and Linux in Flutter 3. Stable doesn't mean identical to mobile—expect platform-specific work for menus, file pickers, window chrome, and installer packaging. Teams ship production desktop apps with Flutter, especially internal tools and cross-platform utilities."
  - q: "How do I build a Flutter desktop release?"
    a: "Enable desktop platforms with flutter config, then run flutter build windows, flutter build macos, or flutter build linux. Outputs land in build/windows/runner/Release, build/macos/Build/Products/Release, and build/linux/x64/release/bundle respectively. Wrap binaries in platform-appropriate installers—MSIX, DMG, or AppImage."
  - q: "What packages help Flutter desktop development?"
    a: "window_manager handles title bar and window sizing; file_picker and path_provider work on desktop; hotkey_manager registers global shortcuts; bitsdojo_window customizes Windows title bar. Test keyboard navigation and mouse hover states—mobile-first widgets often ignore these."
---

Our team had a working iOS app and a stakeholder asking for "the same thing on Windows by Friday." Flutter desktop got us 80% there in a day. The remaining 20%—menu bars, installer signing, multi-window focus, and `TextField` shortcuts—took two weeks. Desktop isn't a free port; it's the same Dart codebase with different platform assumptions you have to explicitly handle.

## Enable and build desktop targets

```bash
flutter config --enable-windows-desktop
flutter config --enable-macos-desktop
flutter config --enable-linux-desktop

flutter create --platforms=windows,macos,linux .
flutter run -d windows
flutter build windows --release
flutter build macos --release
flutter build linux --release
```

Verify `pubspec.yaml` doesn't exclude desktop in plugin declarations. Check each dependency's pub.dev platform badges—mobile-only plugins crash at runtime on desktop.

## Window management

Default window size and constraints:

```dart
import 'package:window_manager/window_manager.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();

  const options = WindowOptions(
    size: Size(1280, 800),
    minimumSize: Size(800, 600),
    center: true,
    titleBarStyle: TitleBarStyle.normal,
  );
  await windowManager.waitUntilReadyToShow(options, () async {
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(MyApp());
}
```

Listen for close events to confirm unsaved work:

```dart
class _AppWindowListener with WindowListener {
  @override
  void onWindowClose() async {
    if (hasUnsavedChanges) {
      final save = await showExitDialog();
      if (save) await saveDocument();
    }
    await windowManager.destroy();
  }
}
```

## Platform menus and shortcuts

**macOS** — native menu bar via `PlatformMenuBar`:

```dart
PlatformMenuBar(
  menus: [
    PlatformMenu(
      label: 'File',
      menus: [
        PlatformMenuItem(
          label: 'Open',
          shortcut: SingleActivator(LogicalKeyboardKey.keyO, meta: true),
          onSelected: _openFile,
        ),
      ],
    ),
  ],
  child: child,
)
```

**Windows/Linux** — in-app menus or `menubar` package. Register accelerators consistently: Ctrl vs Cmd meta key differs—use `Platform.isMacOS` for shortcuts display.

## File system and native dialogs

```dart
final result = await FilePicker.platform.pickFiles(
  type: FileType.custom,
  allowedExtensions: ['pdf', 'docx'],
);

if (result != null) {
  final path = result.files.single.path!;
  await processFile(File(path));
}
```

Use `path_provider` for app support directories:

```dart
final dir = await getApplicationSupportDirectory();
final dbPath = p.join(dir.path, 'app.db');
```

Desktop users expect native file dialogs and standard save/open paths—not mobile share sheets.

## Keyboard and mouse UX

Audit every screen for:

- **Tab traversal** between inputs.
- **Enter to submit** forms.
- **Hover states** on buttons (`MouseRegion` + `MaterialState.hovered`).
- **Context menus** — right-click on list items.
- **Scroll wheel** on custom scroll views.

```dart
MouseRegion(
  onEnter: (_) => setState(() => _hovered = true),
  onExit: (_) => setState(() => _hovered = false),
  child: ElevatedButton(...),
)
```

## Packaging and distribution

**Windows:**

- Build MSIX for Microsoft Store: `flutter pub run msix:create`
- Or traditional installer with Inno Setup / NSIS wrapping `build/windows/runner/Release/`

**macOS:**

- Code sign and notarize—required for Gatekeeper:

```bash
flutter build macos --release
codesign --deep --force --verify --sign "Developer ID" build/macos/Build/Products/Release/my_app.app
xcrun notarytool submit my_app.zip --apple-id ... --team-id ... --password ...
```

- DMG for direct download via `create-dmg` or `appdmg`.

**Linux:**

- Bundle dependencies: `flutter build linux --release`
- Package as AppImage, Snap, or Flatpak depending on target audience.
- Test on target distros—GLIBC version mismatches break binaries.

### CI for desktop builds

GitHub Actions matrix:

```yaml
strategy:
  matrix:
    os: [windows-latest, macos-latest, ubuntu-latest]
steps:
  - run: flutter build ${{ matrix.build_target }} --release
```

macOS notarization needs Apple credentials in secrets. Windows Authenticode signing uses `signtool` post-build.

### Desktop-specific pitfalls

1. **Mobile-only plugins** — `camera`, some `firebase` modules limited; read docs.
2. **Hardcoded Platform.isIOS** — breaks desktop silently.
3. **Touch-only gestures** — add mouse equivalents.
4. **Fixed mobile aspect ratios** — use responsive layouts (`LayoutBuilder`, split views).
5. **Missing auto-update** — integrate `sparkle` (macOS), `winsparkle` (Windows), or custom updater.

Desktop users expect native polish. Budget time for platform QA, not just `flutter run -d windows`.

### Menu bar and system tray on desktop

Windows and Linux users expect system tray icons for background apps:

```dart
// tray_manager package for minimize-to-tray behavior
await trayManager.setIcon('assets/tray_icon.png');
```

macOS menu bar integration uses PlatformMenuBar at app root; don't duplicate hamburger menus from mobile. Test window resize to minimum dimensions—responsive breakpoints differ from phone layouts.

Auto-update strategy differs per store—Microsoft Store handles updates; direct DMG downloads need Sparkle or custom updater. Windows SmartScreen warnings on unsigned executables kill conversion—budget for code signing certificates year one of desktop shipping.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Test window resize and multi-monitor DPI on desktop — Flutter layout that fills mobile screens leaves dead space on 27-inch monitors.

## Resources

- [Flutter desktop support](https://docs.flutter.dev/platform-integration/desktop)
- [window_manager package](https://pub.dev/packages/window_manager)
- [file_picker package](https://pub.dev/packages/file_picker)
- [Apple notarization guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [MSIX packaging for Flutter](https://pub.dev/packages/msix)
