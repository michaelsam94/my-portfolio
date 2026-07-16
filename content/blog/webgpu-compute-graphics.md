---
title: "WebGPU for Compute and Graphics"
slug: "webgpu-compute-graphics"
description: "Get started with WebGPU in the browser: device initialization, compute shaders, render pipelines, and practical use cases for GPU-accelerated web apps."
datePublished: "2026-05-23"
dateModified: "2026-05-23"
tags: ["Web", "WebGPU", "Graphics", "Frontend"]
keywords: "WebGPU, compute shader, GPU, WGSL, render pipeline, browser graphics, parallel computation"
faq:
  - q: "How does WebGPU differ from WebGL?"
    a: "WebGL is based on OpenGL ES 2.0/3.0 — a 15-year-old API designed primarily for graphics with compute added as an afterthought. WebGPU is a modern API modeled after Vulkan, Metal, and Direct3D 12. It provides first-class compute shaders, explicit resource management, and better multi-threading. WebGPU compute shaders are the primary reason to adopt it over WebGL."
  - q: "What is WGSL?"
    a: "WGSL (WebGPU Shading Language) is the default shader language for WebGPU — similar to Rust syntax with C-like constructs. It replaces GLSL used in WebGL. WGSL shaders run on both compute and render pipelines. You write .wgsl files or inline shader strings and create shader modules from them."
  - q: "Can WebGPU run in Web Workers?"
    a: "Yes. WebGPU supports OffscreenCanvas in workers, enabling GPU compute and rendering off the main thread. This is critical for performance — compute shaders processing large datasets won't block UI interactions. Initialize the adapter and device in a worker, run compute passes, and transfer results back via postMessage or shared buffers."
---

WebGL handled our particle visualization until we tried computing 500,000 particle positions on the GPU. The fragment-shader hack worked but was fragile and slow to initialize. WebGPU's compute shaders processed the same workload in 2ms per frame with cleaner code — a dedicated compute pipeline, explicit buffer management, and no graphics API contortions.

## Device initialization

```javascript
async function initWebGPU() {
  if (!navigator.gpu) {
    throw new Error('WebGPU not supported');
  }

  const adapter = await navigator.gpu.requestAdapter();
  const device = await adapter.requestDevice();
  const canvas = document.querySelector('canvas');
  const context = canvas.getContext('webgpu');

  const format = navigator.gpu.getPreferredCanvasFormat();
  context.configure({ device, format, alphaMode: 'premultiplied' });

  return { device, context, format };
}
```

Always check for `navigator.gpu` — WebGPU requires Chrome 113+, Firefox 141+, Safari 26+.

## Compute shader example

Parallel multiplication of two arrays:

```wgsl
// shader.wgsl
@group(0) @binding(0) var<storage, read> inputA: array<f32>;
@group(0) @binding(1) var<storage, read> inputB: array<f32>;
@group(0) @binding(2) var<storage, read_write> output: array<f32>;

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3u) {
  output[id.x] = inputA[id.x] * inputB[id.x];
}
```

```javascript
const shaderModule = device.createShaderModule({ code: shaderCode });

const pipeline = device.createComputePipeline({
  layout: 'auto',
  compute: { module: shaderModule, entryPoint: 'main' },
});

// Create GPU buffers
const bufferA = device.createBuffer({
  size: dataA.byteLength,
  usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
});

device.queue.writeBuffer(bufferA, 0, dataA);

const bindGroup = device.createBindGroup({
  layout: pipeline.getBindGroupLayout(0),
  entries: [
    { binding: 0, resource: { buffer: bufferA } },
    { binding: 1, resource: { buffer: bufferB } },
    { binding: 2, resource: { buffer: outputBuffer } },
  ],
});

// Dispatch compute work
const commandEncoder = device.createCommandEncoder();
const pass = commandEncoder.beginComputePass();
pass.setPipeline(pipeline);
pass.setBindGroup(0, bindGroup);
pass.dispatchWorkgroups(Math.ceil(dataLength / 64));
pass.end();

device.queue.submit([commandEncoder.finish()]);
```

## Render pipeline

Draw a triangle:

```wgsl
@vertex
fn vs_main(@builtin(vertex_index) i: u32) -> @builtin(position) vec4f {
  var pos = array(
    vec2f(0.0, 0.5),
    vec2f(-0.5, -0.5),
    vec2f(0.5, -0.5),
  );
  return vec4f(pos[i], 0.0, 1.0);
}

@fragment
fn fs_main() -> @location(0) vec4f {
  return vec4f(0.2, 0.6, 1.0, 1.0);
}
```

```javascript
const renderPipeline = device.createRenderPipeline({
  layout: 'auto',
  vertex: { module: shaderModule, entryPoint: 'vs_main' },
  fragment: { module: shaderModule, entryPoint: 'fs_main', targets: [{ format }] },
  primitive: { topology: 'triangle-list' },
});

// Render pass
const encoder = device.createCommandEncoder();
const pass = encoder.beginRenderPass({
  colorAttachments: [{
    view: context.getCurrentTexture().createView(),
    clearValue: { r: 0, g: 0, b: 0, a: 1 },
    loadOp: 'clear',
    storeOp: 'store',
  }],
});
pass.setPipeline(renderPipeline);
pass.draw(3);
pass.end();
device.queue.submit([encoder.finish()]);
```

## Practical use cases

| Use case | Pipeline | Why GPU |
|---|---|---|
| Image filters (blur, sharpen) | Compute | Parallel per-pixel operations |
| ML inference | Compute | Matrix multiplication at scale |
| Physics simulation | Compute | Independent particle updates |
| 3D rendering | Render | Triangle rasterization |
| Data visualization | Compute + Render | Process data, then draw |
| Cryptographic hashing | Compute | Parallel hash computation |

## WebGPU vs. alternatives

| API | Compute | Maturity | Browser support |
|---|---|---|---|
| WebGL 2 | Limited (frag shader hack) | Stable | Universal |
| WebGPU | First-class compute shaders | Stable (2024+) | Modern browsers |
| WASM + SIMD | CPU parallel | Stable | Universal |
| Web Workers | CPU parallel | Stable | Universal |

Use WebGPU when data parallelism exceeds what WASM SIMD can deliver. Use WASM for sequential logic and DOM interaction.

## Error handling

```javascript
device.addEventListener('uncapturederror', (e) => {
  console.error('WebGPU error:', e.error.message);
});

// Validate in development
const validationEnabled = device.features.has('shader-f16');
```

Wrap initialization in try/catch — adapter or device requests can fail on unsupported hardware.

## Buffer management

GPU buffers persist across frames. Reuse buffers instead of creating new ones each frame:

```javascript
// Reuse buffer, update contents
device.queue.writeBuffer(uniformBuffer, 0, newUniformData);
```

Create buffers with `GPUBufferUsage.COPY_DST | GPUBufferUsage.UNIFORM` for data updated every frame.

## Fallback rendering

Feature-detect WebGPU and fall back to WebGL2 or Canvas2D:

```javascript
if (!navigator.gpu) {
  initWebGL2Renderer();
  return;
}
```

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

## Resources

- [WebGPU specification (W3C)](https://www.w3.org/TR/webgpu/)
- [MDN: WebGPU API](https://developer.mozilla.org/en-US/docs/Web/API/WebGPU_API)
- [WGSL specification](https://www.w3.org/TR/WGSL/)
- [WebGPU fundamentals (webgpufundamentals.org)](https://webgpufundamentals.org/)
- [Can I use WebGPU](https://caniuse.com/webgpu)
