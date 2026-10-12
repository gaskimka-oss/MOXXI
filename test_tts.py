import asyncio
import edge_tts

async def main():
    text = "Привет! Это проверка нейросети Мокси два ноль."
    comm = edge_tts.Communicate(text, 'ru-RU-SvetlanaNeural', rate='+6%')
    await comm.save('test_audio_moxxi.mp3')
    print("TTS SUCCESS!")

if __name__ == "__main__":
    asyncio.run(main())
