# Regiões aceitas e rejeitadas

O console da leitura única e contínua agora mostra contagens separadas de mesas aceitas para leitura e regiões rejeitadas. Regiões rejeitadas exibem status, código original e explicação em português, sem campos Hero que poderiam sugerir tentativa de OCR.

Isso não é um classificador de lobby. FULL_BOUNDARY_NOT_ESTABLISHED significa limites completos não confirmados; não prova que a região seja lobby. Os critérios de detecção e leitura permanecem inalterados. O número da região vale somente para aquela captura, sem identidade persistente.

Validação local: 20 testes de apresentação, observador e pipeline passaram. O motivo da rejeição no caso real anterior ainda não foi registrado; será visível na próxima execução. Não há novas gravações de imagens ou logs.
