---
title: "Fragment Shaders in Flutter"
slug: "flutter-shaders-fragment-programs"
description: "Custom GLSL fragment shaders in Flutter unlock effects like ripples, gradients, and post-processing. FragmentProgram loading and ShaderMask integration."
datePublished: "2025-03-14"
dateModified: "2025-03-14"
tags: ["Flutter", "Dart", "Shaders", "Mobile"]
keywords: "Flutter fragment shader, FragmentProgram GLSL, custom shader Flutter, flutter_shaders, GPU effects Flutter"
faq:
  - q: "Do Flutter fragment shaders work on all platforms?"
    a: "Supported on Impeller and Skia backends for mobile and desktop; web support evolves—verify target platforms in current Flutter release notes. Always test on physical devices, not only simulators."
  - q: "Where do I put .frag shader files?"
    a: "Under shaders/ directory declared in pubspec.yaml flutter shaders section. Flutter compiles GLSL to platform-appropriate formats at build time."
  - q: "Fragment shader vs CustomPainter?"
    a: "CustomPainter draws with Canvas CPU/GPU primitives—great for charts and paths. Fragment shaders run per-pixel on GPU—better for complex color transforms, noise, blur-like effects impossible to paint efficiently with Dart loops."
---

We wanted a water-ripple touch effect on a hero image. `CustomPainter` at 60 FPS melted a Pixel 4. Sixty lines of GLSL in a fragment shader ran at 3 ms raster time because the GPU does what CPUs should not—per-pixel math in parallel.

Flutter 3+ supports user-authored fragment shaders via `FragmentProgram` and `FragmentShader` widgets.

## Project setup

`pubspec.yaml`:

```yaml
flutter:
  shaders:
    - shaders/ripple.frag
```

`ripple.frag` (simplified):

```glsl
#version 460 core

#include <flutter/runtime_effect.glsl>

uniform vec2 uSize;
uniform float uTime;
uniform vec2 uTouch;

out vec4 fragColor;

void main() {
  vec2 uv = FlutterFragCoord().xy / uSize;
  vec2 center = uTouch / uSize;
  float dist = distance(uv, center);
  float wave = sin(dist * 30.0 - uTime * 4.0) * 0.02;
  vec2 distorted = uv + normalize(uv - center) * wave;
  fragColor = vec4(distorted, 0.0, 1.0);
}
```

Consult Flutter's GLSL include for `FlutterFragCoord()` and uniform conventions—they differ slightly from raw OpenGL tutorials.

## Loading the program

```dart
late FragmentProgram _program;

Future<void> loadShader() async {
  _program = await FragmentProgram.fromAsset('shaders/ripple.frag');
}
```

Load once at startup or lazy-first-use; compilation stutters first frame.

## Applying with ShaderMask or CustomPaint

```dart
class RippleImage extends StatefulWidget {
  @override
  State<RippleImage> createState() => _RippleImageState();
}

class _RippleImageState extends State<RippleImage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _time;
  Offset _touch = Offset.zero;
  FragmentShader? _shader;

  @override
  void initState() {
    super.initState();
    _time = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    )..repeat();
    _load();
  }

  Future<void> _load() async {
    final program = await FragmentProgram.fromAsset('shaders/ripple.frag');
    setState(() => _shader = program.fragmentShader());
  }

  @override
  Widget build(BuildContext context) {
    final shader = _shader;
    if (shader == null) return const SizedBox.shrink();

    return GestureDetector(
      onPanUpdate: (d) => setState(() => _touch = d.localPosition),
      child: AnimatedBuilder(
        animation: _time,
        builder: (context, child) {
          shader
            ..setFloat(0, context.size?.width ?? 1)
            ..setFloat(1, context.size?.height ?? 1)
            ..setFloat(2, _time.value)
            ..setFloat(3, _touch.dx)
            ..setFloat(4, _touch.dy);
          return CustomPaint(
            painter: _ShaderPainter(shader),
            child: child,
          );
        },
        child: Image.asset('assets/hero.png', fit: BoxFit.cover),
      ),
    );
  }
}
```

Uniform index order matches GLSL declaration order—verify with Flutter docs when upgrading SDK.

## SKSL warm-up and jank

First shader use compiles at runtime. Warm up off-screen during splash:

```dart
await FragmentProgram.fromAsset('shaders/ripple.frag');
```

Ship minimal shader set; compilation cost scales with complexity.

## Impeller vs Skia

Impeller is default on iOS and increasingly Android. Shader behavior should match but test both backends during Flutter upgrades—GLSL support tightens over time.

## Debugging failed shaders

Build errors print GLSL line numbers in console. Common issues: wrong `#version`, missing `flutter/runtime_effect.glsl`, invalid uniform types.

## When shaders are overkill

Simple gradients and blurs often exist as widgets (`ShaderMask`, `BackdropFilter`). Reach for fragment shaders when effect is pixel-math heavy or art-directed in GLSL.

## Uniform layout pitfalls

After Flutter SDK upgrade, uniform indices may shift—document SDK version in shader README. Wrap uniform setup:

```dart
void configureShader(FragmentShader shader, Size size, double time) {
  shader.setFloat(_Uniform.time, time);
  shader.setFloat(_Uniform.width, size.width);
  shader.setFloat(_Uniform.height, size.height);
}
```

## Fallback for unsupported platforms

```dart
if (!await FragmentProgram.fromAsset('shaders/ripple.frag').catchError((_) => null)) {
  return const StaticGradientBackground();
}
```

Web may lag mobile shader support—feature-detect per target.

## Asset size

Ship minimal shader set; compress or simplify GLSL loops if compile time spikes on older GPUs.


## Coordinate systems

Flutter fragment shaders use normalized or pixel coords depending on API—read current doc for `FlutterFragCoord` vs custom uniforms; mixing up Y-flip causes upside-down effects.

## Battery impact

Full-screen shader animating every frame drains battery—pause animation when app backgrounded via `WidgetsBindingObserver`.

## Testing

Golden tests unreliable for shaders—capture screenshot on device farm reference devices for visual QA baseline.

## Gradual rollout

Feature-flag shader-heavy screens; monitor crash rate and frame time in production analytics before 100% rollout.

## Hot reload limitation

Shader file changes require hot restart not hot reload—document in team README to prevent "shader not updating" support threads in Slack.

## Rollout guidance

Shader effects marketing demo video recorded release day—support team uses video explaining expected visual reducing tickets user thinks app glitchy when intentional effect.

## Team practices

Shipping Flutter Shaders Fragment Programs in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Shaders Fragment Programs, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Shaders Fragment Programs PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Shaders Fragment Programs questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Shaders Fragment Programs spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

## Resources

- [Writing and using fragment shaders (Flutter docs)](https://docs.flutter.dev/ui/design/graphics/fragment-shaders)
- [FragmentProgram API](https://api.flutter.dev/flutter/dart-ui/FragmentProgram-class.html)
- [Flutter shader examples (GitHub)](https://github.com/flutter/flutter/tree/master/examples/shaders)
- [Impeller rendering engine](https://docs.flutter.dev/perf/impeller)
- [GLSL reference (Khronos)](https://www.khronos.org/opengl/wiki/OpenGL_Shading_Language)
