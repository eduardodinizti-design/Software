"""Percepção por VISÃO (YOLO) — pacote da migração 20/11 (ver memória
nvt-visao-yolo-decisao). Substitui a injeção Frida como percepção PADRÃO:
screenshot -> detecção de objetos (YOLO) -> o MESMO table_state que
protobuf_state/suprema_state alimentam no cérebro. Crash-free (não injeta),
universal (um modelo p/ todos os sites) e multi-mesa por clustering espacial.

F0 (este commit): estrutura + esquema de classes (classes.py) + interface do
adaptador (vision_state.py) com o clustering espacial. SEM modelo treinado
ainda (F1 dataset por auto-rotulagem, F2 treino, F3 vision_state ao vivo + OCR
dos números, F4 validação lado-a-lado e plug no operador).
"""
