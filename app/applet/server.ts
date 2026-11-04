import express from 'express';
import cors from 'cors';
import { GoogleGenAI } from '@google/genai';
import path from 'path';

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Inicializa o SDK oficial @google/genai
const ai = new GoogleGenAI();

app.post('/api/analyze-table', async (req, res) => {
  try {
    const { image_base64 } = req.body;
    if (!image_base64) {
      return res.status(400).json({ error: 'image_base64 is required' });
    }

    // Remove prefixo data:image/... se houver
    const base64Data = image_base64.replace(/^data:image\/\w+;base64,/, '');

    const prompt = `Analyze this PPPoker table screenshot. Return a JSON object with the following structure:
{
  "hero_cards": ["As", "Kh"], // exact rank and suit (s, h, d, c)
  "board_cards": ["Jd", "5s", "3c"], // community cards visible on table
  "pot_size": "3.7 BB",
  "active_actions": ["FOLD", "CALL/CHECK"],
  "raise_slider": "2.0 BB",
  "hand_evaluation": "Top Pair / Flush Draw",
  "confidence": 0.98
}
Be extremely precise. Only return valid JSON.`;

    const response = await ai.models.generateContent({
      model: 'gemini-3.8-flash',
      contents: [
        {
          inlineData: {
            mimeType: 'image/png',
            data: base64Data
          }
        },
        prompt
      ]
    });

    const textOutput = response.text || '{}';
    // Limpar markdown code blocks se houver
    const cleanedJson = textOutput.replace(/```json/g, '').replace(/```/g, '').trim();
    const parsed = JSON.parse(cleanedJson);

    return res.json({
      status: 'SUCCESS',
      analysis: parsed
    });
  } catch (error: any) {
    console.error('Error in /api/analyze-table:', error);
    return res.status(500).json({ status: 'ERROR', message: error.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`[VisualPilot Server] Running on port ${PORT}`);
});
