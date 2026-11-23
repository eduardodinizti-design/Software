"""Treina o detector de cartas/objetos YOLOv8 no dataset sintetico. Auto-detecta GPU (CUDA):
na RTX 4060 usa yolov8s + mais epochs + imgsz 960 (treino de VERDADE, minutos). Sem GPU,
cai p/ nano/CPU. Uso: python -I vision_yolo/train.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "dataset", "data.yaml")


def main():
    import torch
    from ultralytics import YOLO
    if not os.path.exists(DATA):
        print("[erro] rode make_train_data.py antes:", DATA); return 1
    gpu = torch.cuda.is_available()
    print("[train] CUDA=%s device=%s" % (gpu, torch.cuda.get_device_name(0) if gpu else "CPU"))
    # converge em ~6-8 epocas; imgsz 768 cobre as capturas reais (~920px) e acelera ~2-3x.
    if gpu:
        model, kw = YOLO("yolov8s.pt"), dict(epochs=40, imgsz=768, batch=24, device=0)
    else:
        model, kw = YOLO("yolov8n.pt"), dict(epochs=45, imgsz=768, batch=8, device="cpu")
    model.train(data=DATA, patience=15, project=os.path.join(HERE, "runs"),
                name="cards", exist_ok=True, verbose=True, plots=True, **kw)
    print("[train] fim. melhor peso em runs/cards/weights/best.pt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
