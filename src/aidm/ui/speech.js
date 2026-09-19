// Reads one exchange aloud, a line at a time, as each clip lands.
export default {
  // A real element, so dice_sound.js sees a line being read and holds its click.
  template: '<audio ref="audio"></audio>',
  data() {
    return { urls: [], cursor: 0, armed: false, generation: 0, playingGeneration: 0 };
  },
  mounted() {
    this.audio = this.$refs.audio;
    this.audio.addEventListener("ended", () => this.ended());
    this.audio.addEventListener("error", () => this.stop());
  },
  methods: {
    follow(urls, restart) {
      this.urls = urls;
      if (restart) {
        this.cursor = 0;
        this.armed = true;
        this.generation++;
      }
      this.advance();
    },
    playFrom(urls, index) {
      this.audio.pause();
      this.urls = urls;
      this.cursor = index;
      this.armed = true;
      this.generation++;
      this.advance();
    },
    stop() {
      this.armed = false;
      this.audio.pause();
      this.report();
    },
    advance() {
      if (!this.armed || !this.audio.paused) return;
      const url = this.urls[this.cursor];
      if (url === undefined) {
        this.armed = false;
        this.report();
        return;
      }
      if (url === null) return;
      this.audio.src = url;
      this.playingGeneration = this.generation;
      // Autoplay policy before the first gesture: the line's own button then starts it.
      this.audio.play().catch(() => this.stop());
      this.report();
    },
    ended() {
      // A restart mid-line keeps its own cursor: the line that just ended was the old one's.
      if (this.playingGeneration === this.generation) this.cursor++;
      this.advance();
    },
    report() {
      const reading = this.armed && !this.audio.paused;
      this.$emit("reading", reading ? this.urls[this.cursor] : "");
    },
  },
};
