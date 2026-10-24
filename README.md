# ig-goog-lesheets

Очередь Reels для Instagram @goog.lesheets (Google Таблицы для малого бизнеса, Сочи). Ведётся автоматически Claude.

- `queue.json` — очередь: id, дата, статус (ready/published), подпись, хештеги, путь к видео
- `reels/` — готовые ролики, `specs/` — сцены роликов
- `scripts/reelgen.py`, `scripts/render_reel.py` — генератор (Python + Pillow + imageio-ffmpeg)
- `journal.md` — журнал и статистика, `plan.md` — темы следующих роликов
