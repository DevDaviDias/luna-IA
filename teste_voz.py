import asyncio
import edge_tts

async def test():
    tts = edge_tts.Communicate(
        'Oi! Eu sou a Luna, sua assistente virtual! Prazer em te conhecer~',
        voice='pt-BR-FranciscaNeural',
        rate='+25%',
        pitch='+15Hz'
    )
    await tts.save('teste_luna.mp3')
    print('Salvo!')

asyncio.run(test())