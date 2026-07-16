---
title: "TinyML at the Edge"
slug: "iot-edge-ml-tinyml"
description: "Run machine learning on microcontrollers with TinyML: model quantization, TensorFlow Lite Micro, inference on ARM Cortex-M and ESP32, and when edge ML beats cloud."
datePublished: "2025-08-03"
dateModified: "2025-08-03"
tags: ["IoT", "Embedded", "Performance", "Architecture"]
keywords: "TinyML, edge machine learning, TensorFlow Lite Micro, model quantization, ESP32 ML, microcontroller inference, on-device AI"
faq:
  - q: "What is TinyML?"
    a: "TinyML runs machine learning inference on microcontrollers and embedded devices with kilobytes to low megabytes of memory — no cloud, no OS required. Models are heavily quantized (int8) to fit in flash and run inference in milliseconds on ARM Cortex-M, ESP32, or similar chips costing under $5."
  - q: "When should I run ML at the edge instead of in the cloud?"
    a: "When latency must be under 100ms (anomaly detection on rotating equipment), connectivity is unreliable (remote sensors), privacy requires on-device processing (voice commands, camera feeds), or cloud inference cost exceeds the device cost (millions of devices polling continuously)."
  - q: "How big can a TinyML model be?"
    a: "Typical limits: 20-500 KB quantized model size, 20-200 KB RAM for inference tensor arena, inference time 10-100ms on Cortex-M4 at 80 MHz. A keyword spotting model fits in 20 KB; a person detection model needs 250 KB. Beyond 1 MB, consider an edge gateway with a Linux SBC and full TFLite instead."
---

Cloud ML is powerful and expensive at scale. Sending 100 audio samples per second from 1,000 microphones to classify "normal vs anomalous" costs real money in bandwidth and inference compute. Run a 20 KB quantized model on the microphone's MCU and you get sub-10ms classification, zero cloud dependency, and a BOM increase of roughly zero. TinyML isn't about running GPT on a chip — it's about running the specific classifier you need, on the device that's already collecting the data.

## The TinyML pipeline

```
Training (cloud/GPU)  →  Quantization  →  Conversion  →  Deployment  →  Inference (MCU)
PyTorch/TF model         int8 PTQ/QAT      TFLite .tflite   Flash/RAM      Cortex-M / ESP32
```

You train normally, then compress for deployment. The model that trains at float32 isn't the model that runs on-device.

## Model quantization

Quantization converts float32 weights to int8, shrinking the model ~4x:

```python
import tensorflow as tf

# Post-training quantization
converter = tf.lite.TFLiteConverter.from_saved_model("saved_model/")
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.int8]
converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8

# Representative dataset for calibration
def representative_dataset():
    for i in range(100):
        yield [load_sample(i)]

converter.representative_dataset = representative_dataset
tflite_model = converter.convert()

with open("model_int8.tflite", "wb") as f:
    f.write(tflite_model)
```

PTQ (post-training quantization) is fast but may lose 1-3% accuracy. QAT (quantization-aware training) retrains with simulated int8 ops — better accuracy, more effort.

## TensorFlow Lite Micro on ESP32

```cpp
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "model.h"  // converted .tflite as C array

constexpr int kTensorArenaSize = 30 * 1024;
uint8_t tensor_arena[kTensorArenaSize];

tflite::MicroMutableOpResolver<10> resolver;
resolver.AddConv2D();
resolver.AddMaxPool2D();
resolver.AddFullyConnected();
resolver.AddSoftmax();

tflite::MicroInterpreter interpreter(
    tflite::GetModel(g_model), resolver, tensor_arena, kTensorArenaSize);

interpreter.AllocateTensors();

// Run inference
float* input = interpreter.input(0)->data.f;
memcpy(input, sensor_data, input_size * sizeof(float));

if (interpreter.Invoke() == kTfLiteOk) {
    float* output = interpreter.output(0)->data.f;
    int predicted_class = argmax(output, num_classes);
}
```

The tensor arena is a fixed memory pool — no malloc. Size it by running the model once and checking `interpreter.arena_used_bytes()`.

## Practical example: vibration anomaly detection

Detect bearing failure from accelerometer data:

1. **Collect training data** — normal vibration signatures + labeled failure samples from test rig
2. **Train a 1D CNN** — input: 256-sample window at 1.6 kHz, output: normal/anomaly/bearing_wear
3. **Quantize to int8** — model shrinks from 800 KB to 45 KB
4. **Deploy on STM32L4** — 80 MHz, 128 KB RAM, inference in 35ms
5. **Alert locally** — GPIO pin triggers warning light; MQTT alert sent if connected

```python
# Training model (runs on cloud)
model = tf.keras.Sequential([
    tf.keras.layers.Conv1D(16, 3, activation='relu', input_shape=(256, 1)),
    tf.keras.layers.MaxPool1D(2),
    tf.keras.layers.Conv1D(32, 3, activation='relu'),
    tf.keras.layers.GlobalAveragePooling1D(),
    tf.keras.layers.Dense(3, activation='softmax'),
])
model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
model.fit(X_train, y_train, epochs=50, validation_split=0.2)
```

On-device: sample accelerometer at 1.6 kHz, fill 256-sample buffer, run inference every 256 samples, alert on anomaly class with confidence > 0.85.

## When TinyML vs cloud vs edge gateway

| Factor | TinyML (MCU) | Edge Gateway (Linux) | Cloud |
|--------|--------------|---------------------|-------|
| Latency | <10ms | 50-500ms | 200ms-2s |
| Model size | <500 KB | <50 MB | Unlimited |
| Power | mW | Watts | N/A |
| Connectivity | None needed | Intermittent OK | Required |
| Cost per device | $0 marginal | $50-200 gateway | Per-inference |
| Update model | OTA flash | OTA package | Deploy instantly |

Use TinyML when the sensor node itself needs to decide. Use an edge gateway when you need larger models (object detection, speech). Use cloud when latency and connectivity aren't constraints.

## Data collection for training

On-device ML quality depends on training data representativeness:

1. **Collect on-target hardware** — a model trained on desktop spectrograms may fail on the MCU's ADC noise floor
2. **Label failure modes explicitly** — "bearing wear" and "imbalance" beat a binary normal/anomaly label
3. **Include operating conditions** — train across temperature and load ranges the device will actually see
4. **Hold out entire devices** — split by device, not by time window, to detect overfitting

Export training data during a calibration period, train in the cloud, deploy the quantized `.tflite` via OTA.

## Debugging on-device inference

Common issues:

- **Arena too small** — `AllocateTensors()` fails. Increase `kTensorArenaSize`.
- **Accuracy drop after quantization** — use QAT or a larger representative dataset.
- **Slow inference** — profile with `interpreter.GetLastInferenceTimeMicros()`. Consider CMSIS-NN optimized kernels for ARM.
- **Input preprocessing mismatch** — normalization done during training must match on-device (same scale, offset, window size).

## Common production mistakes

Teams get edge ml tinyml wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of edge ml tinyml fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When edge ml tinyml misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [TensorFlow Lite Micro](https://www.tensorflow.org/lite/microcontrollers) — official guide for MCU deployment
- [Edge Impulse](https://www.edgeimpulse.com/) — end-to-end TinyML platform with data collection and auto-quantization
- [CMSIS-NN](https://github.com/ARM-software//CMSIS-NN) — ARM-optimized neural network kernels for Cortex-M
- [TinyML Foundation](https://www.tinyml.org/) — community, courses, and deployment best practices
