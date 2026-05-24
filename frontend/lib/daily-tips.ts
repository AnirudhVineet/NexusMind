export type DailyTip = {
  category: "Study" | "Productivity" | "Memory" | "Knowledge" | "Mindset" | "Fact";
  title: string;
  body: string;
};

export const DAILY_TIPS: DailyTip[] = [
  { category: "Study", title: "The Feynman Technique", body: "If you can't explain a concept in plain language to a curious 12-year-old, you don't yet understand it. Teach to learn." },
  { category: "Memory", title: "Spaced repetition beats cramming", body: "Reviewing material across days (1, 3, 7, 14 days) burns it into long-term memory far better than re-reading for hours the night before." },
  { category: "Knowledge", title: "Knowledge is a graph, not a list", body: "Facts you can connect to three other things stick. Isolated facts evaporate within a week. Always ask: what does this remind me of?" },
  { category: "Productivity", title: "Two-minute rule", body: "If a task takes under two minutes, do it now. Capturing, scheduling, and re-reading it later costs more than the task itself." },
  { category: "Mindset", title: "Strong opinions, weakly held", body: "Commit to a view confidently enough to act on it, but be ready to drop it the moment better evidence appears. The cost of stubbornness compounds." },
  { category: "Fact", title: "Reading is faster than listening", body: "An average adult reads ~250 words/min and speaks ~150. For dense information, your eyes will beat your ears every time." },
  { category: "Study", title: "Active recall > passive review", body: "Close the book and try to recall. Each retrieval physically strengthens the memory trace — re-reading does almost nothing." },
  { category: "Memory", title: "Sleep is when learning gets saved", body: "The hippocampus replays your day during deep sleep, consolidating it into the cortex. Skipping sleep skips the save." },
  { category: "Knowledge", title: "The curse of expertise", body: "Experts forget what it's like to not know. When learning from one, ask: 'what's the dumb question I should be asking right now?'" },
  { category: "Productivity", title: "Single-task on hard problems", body: "Context switching costs ~23 minutes of focus per switch. Deep work isn't a luxury — it's an order-of-magnitude productivity multiplier." },
  { category: "Mindset", title: "You are what you repeat", body: "Identity follows habit, not the other way around. 'I am a person who reads daily' is built one day at a time." },
  { category: "Fact", title: "Working memory holds ~4 items", body: "Not 7±2, as the old myth goes — modern research puts it at four. Chunk information aggressively." },
  { category: "Study", title: "Interleave your practice", body: "Mixing topics (A, B, C, A, B, C) feels harder than blocking (A, A, A) but produces dramatically better retention and transfer." },
  { category: "Memory", title: "Emotion is memory's glue", body: "You remember where you were on 9/11 but not last Tuesday. Find the human, surprising, or vivid angle in dry material." },
  { category: "Knowledge", title: "Mental models compound", body: "Charlie Munger keeps ~100 mental models from many disciplines. Each new one multiplies the value of the others — start collecting." },
  { category: "Productivity", title: "Write to think", body: "If you can't write it down clearly, you don't understand it. Writing forces the fuzzy ideas in your head to commit to a shape." },
  { category: "Mindset", title: "Comparison is the thief of joy", body: "Compare yourself only to who you were yesterday. Other people's highlights make for a terrible benchmark." },
  { category: "Fact", title: "Caffeine peaks at 30-60 minutes", body: "And its half-life is 5-6 hours. A 3pm coffee is still half-active in your system at 9pm — which is why your sleep suffers." },
  { category: "Study", title: "Teach what you learned today", body: "Even explaining it to a rubber duck works. Verbalizing forces you to find and fill the gaps your eyes glossed over." },
  { category: "Memory", title: "Method of loci", body: "Place facts inside rooms of a familiar house. Memory athletes use this 2,500-year-old trick to remember decks of cards in minutes." },
  { category: "Knowledge", title: "Read the bibliography", body: "The best book on any topic is usually cited in the second-best book. Follow citations upstream — it's compounded curation." },
  { category: "Productivity", title: "Energy beats time management", body: "An hour at peak focus is worth four at low energy. Schedule your hardest work for when you're sharpest, not just when it fits." },
  { category: "Mindset", title: "The ten-thousand-hour rule is a myth", body: "What matters is deliberate practice: at the edge of your ability, with feedback, repeatedly. Hours alone produce plateaus, not mastery." },
  { category: "Fact", title: "Your brain is 2% of your body weight", body: "But it uses ~20% of your energy. Thinking is metabolically expensive — that's why hard problems make you tired and hungry." },
  { category: "Study", title: "Pomodoro: 25 on, 5 off", body: "Short bursts of intense focus with real breaks outperform long marathons. The break lets your brain consolidate what you just did." },
  { category: "Memory", title: "Names: use them three times", body: "Repeat someone's name in the first minute (greeting, question, parting). The third repetition moves it from working to long-term memory." },
  { category: "Knowledge", title: "First principles thinking", body: "Strip an idea down to what you know is true, then rebuild upward. Most 'rules' are inherited assumptions nobody questioned." },
  { category: "Productivity", title: "Inbox zero is a trap", body: "The goal isn't an empty inbox; it's an empty mind. Process to action, archive, or delete — but don't measure success by the count." },
  { category: "Mindset", title: "Done > perfect", body: "A shipped 80% solution teaches you more than a polished 100% that never sees the world. Ship, learn, iterate." },
  { category: "Fact", title: "Sleep cycles are 90 minutes", body: "Wake at the end of one and you feel rested; wake mid-cycle and you feel destroyed. Time your alarm in 90-minute multiples from sleep onset." },
  { category: "Study", title: "Mistakes are the curriculum", body: "Getting a problem wrong and then learning why creates 4x the retention of getting it right the first time. Seek out hard problems." },
  { category: "Memory", title: "Sketch, don't just highlight", body: "Drawing a concept (even crudely) recruits visual + motor memory on top of verbal. Highlighting recruits almost nothing." },
  { category: "Knowledge", title: "Steelman before you criticize", body: "Argue your opponent's position better than they can. If you still disagree, your disagreement is informed. If not, you learned something." },
  { category: "Productivity", title: "Decisions in the morning", body: "Decision fatigue is real. Obama wore the same suit every day for this reason. Save your willpower for things that matter." },
  { category: "Mindset", title: "Confidence comes from evidence", body: "Not from affirmations. The fastest way to feel competent is to actually become competent — through small, repeated wins." },
  { category: "Fact", title: "Multitasking doesn't exist", body: "Your brain doesn't run two cognitive tasks in parallel — it switches rapidly, leaking ~20% efficiency per switch. 'Multitasker' = 'task switcher.'" },
  { category: "Study", title: "Make connections, not collections", body: "A library of notes you never re-read is a graveyard. The value of a knowledge base is in the links between ideas, not the count." },
  { category: "Memory", title: "Use the spacing effect", body: "Reviewing the same material on days 1, 3, 7, 21 takes less total time than re-reading it for an hour straight — and remembers 3x better." },
  { category: "Knowledge", title: "Read old books", body: "If a book has survived 100 years, it has been filtered by millions of readers. Today's bestseller has been filtered by marketing." },
  { category: "Productivity", title: "Default to one thing per day", body: "If you accomplished one important thing today, today was a win. Aiming for three usually means accomplishing zero." },
  { category: "Mindset", title: "Curiosity scales; willpower doesn't", body: "Forcing yourself to study a topic you hate fails after a week. Finding the angle that fascinates you sustains you for years." },
  { category: "Fact", title: "The brain prunes what it doesn't use", body: "Unused neural pathways are physically removed during sleep. 'Use it or lose it' isn't a metaphor — it's neurobiology." },
  { category: "Study", title: "Concept maps reveal blind spots", body: "Draw the topic from memory as a diagram. The empty spaces and broken arrows show you exactly what you don't yet understand." },
  { category: "Memory", title: "Smell is the strongest memory cue", body: "The olfactory bulb wires directly into the hippocampus and amygdala. A scent can resurrect a 20-year-old memory in a second." },
  { category: "Knowledge", title: "Beware the expert paradox", body: "The more you know about a field, the more you realize how much you don't know. Confidence drops before it climbs again." },
  { category: "Productivity", title: "Constraints breed creativity", body: "Unlimited time + unlimited scope = paralysis. Give yourself a tight deadline or a hard limit and watch your ingenuity wake up." },
  { category: "Mindset", title: "Boredom is information", body: "It's your brain saying 'this isn't worth the cost.' Don't medicate it with scrolling — listen to it and change something." },
  { category: "Fact", title: "We forget 50% within an hour", body: "Without review, half of new information is gone in 60 minutes (Ebbinghaus, 1885). With one review the next day, retention jumps to 90%." },
  { category: "Study", title: "Question while you read", body: "Pause every paragraph and ask: 'do I agree?' 'what's the counter-argument?' 'how would I explain this?' Passive reading is theatre." },
  { category: "Memory", title: "Chunking expands working memory", body: "You can't hold 11 random digits — but a chess grandmaster holds an entire board because the pieces form known patterns. Build vocabularies of patterns." },
  { category: "Knowledge", title: "The map is not the territory", body: "All models are wrong; some are useful. Hold every concept loosely — including this one." },
  { category: "Productivity", title: "Friction is the killer", body: "If your journal is in a drawer, you won't write. If it's on your desk, you might. Lower the friction for habits you want; raise it for habits you don't." },
  { category: "Mindset", title: "Imposter syndrome is universal", body: "Even Nobel laureates report feeling like frauds. It's a sign you care, not a sign you're inadequate. Keep going." },
  { category: "Fact", title: "Walking unsticks ideas", body: "Stanford found that walking boosts creative output by ~60% vs sitting. Stuck on a problem? Stop solving and start walking." },
  { category: "Study", title: "Pre-test yourself", body: "Take a quiz on material BEFORE you study it. Even random guessing primes your brain to encode the right answer when you encounter it." },
  { category: "Memory", title: "Stories outlive facts", body: "We've forgotten Aristotle's logical proofs but remember Aesop's fables. Wrap dry facts in narrative and they outlive you." },
  { category: "Knowledge", title: "Inversion: think backwards", body: "Don't ask 'how do I succeed?' Ask 'how do I guarantee failure?' Then don't do that. Charlie Munger's favorite tool." },
  { category: "Productivity", title: "The first hour sets the day", body: "Spend it on the most important thing — not email, not Slack. Whatever you do first gets your sharpest, freshest mind." },
  { category: "Mindset", title: "Process over outcome", body: "You can play poker perfectly and lose, or terribly and win. Judge the quality of your decisions by the quality of your reasoning, not the result." },
  { category: "Fact", title: "Your microbiome talks to your brain", body: "Gut bacteria produce ~90% of your serotonin. What you eat literally affects what you think — the 'gut-brain axis' is real." },
];

export function getTodaysTip(date: Date = new Date()): DailyTip {
  // Deterministic per-day index — same tip for everyone on the same calendar day.
  // Using YYYY-MM-DD as a string and hashing keeps the cycle stable across timezones
  // for a single user (their local midnight rotates the tip).
  const key = `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % DAILY_TIPS.length;
  return DAILY_TIPS[idx];
}
