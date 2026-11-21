"""Treina o detector de cartas YOLOv8n no dataset sintetico. CPU (sem GPU) -> modelo nano,
poucos epochs p/ um 1o prototipo. Uso: python -I vision_yolo/train.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "dataset", "data.yaml")


def main():
    from ultralytics import YOLO
    if not os.path.exists(DATA):
        print("[erro] rode make_train_data.py antes:", DATA); return 1
    model = YOLO("yolov8n.pt")                      # baixa ~6MB na 1a vez (transfer learning)
    model.train(data=DATA, epochs=45, imgsz=768, batch=8, patience=12,
                project=os.path.join(HERE, "runs"), name="cards", exist_ok=True,
                verbose=True, plots=False)
    print("[train] fim. melhor peso em runs/cards/weights/best.pt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
