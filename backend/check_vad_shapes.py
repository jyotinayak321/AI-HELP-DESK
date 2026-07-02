import onnxruntime as ort

s = ort.InferenceSession('local_models/silero_vad.onnx', providers=['CPUExecutionProvider'])

print("=== INPUTS ===")
for i in s.get_inputs():
    print(i.name, i.shape, i.type)

print("=== OUTPUTS ===")
for o in s.get_outputs():
    print(o.name, o.shape, o.type)