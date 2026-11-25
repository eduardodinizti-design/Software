"""Valida o detector YOLO treinado nas CAPTURAS REAIS: roda a inferencia, desenha as
deteccoes (classe+conf) e salva. Mostra se a VISAO le as cartas da tela de verdade.
Uso: python -I vision_yolo/validate_on_real.py <img1> <img2> ..."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))


def main(argv):
    from PIL import Image, ImageDraw
    from vision_yolo.detect import CardDetector
    imgs = argv or [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                 "research", "suprema_cocos", "slider_shot.png")]
    det = CardDetector()
    for p in imgs:
        if not os.path.exists(p):
            print("[skip] nao existe:", p); continue
        img = Image.open(p).convert("RGB"); W, H = img.size
        dets = det.detect(p, conf=0.25)
        d = ImageDraw.Draw(img)
        cards = []
        for de in dets:
            x0, y0, x1, y1 = (de.box[0]*W, de.box[1]*H, de.box[2]*W, de.box[3]*H)
            col = (255, 0, 255) if de.is_card else (0, 200, 255)
            d.rectangle([x0, y0, x1, y1], outline=col, width=3)
            d.text((x0, y0-14), "%s %.2f" % (de.name, de.conf), fill=col)
            if de.is_card:
                cards.append(de.name)
        out = os.path.splitext(p)[0] + "_yolo.png"
        img.save(out)
        print("[%s] %d deteccoes | cartas: %s -> %s" % (os.path.basename(p), len(dets), cards, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
