// One click when dice land on the card.
const SOUND_KEY = "aidm.dice.sound";

export default {
  template: "<div></div>",
  props: { src: String },
  mounted() {
    this.audio = new Audio(this.src);
    this.$emit("sound", this.soundOn());
  },
  methods: {
    play() {
      if (!this.soundOn() || this.narrating()) return;
      this.audio.currentTime = 0;
      // Autoplay policy before the first gesture is not an error the player reads.
      this.audio.play().catch(() => {});
    },
    toggleSound() {
      const on = !this.soundOn();
      localStorage.setItem(SOUND_KEY, on ? "on" : "off");
      this.$emit("sound", on);
    },
    soundOn() {
      return localStorage.getItem(SOUND_KEY) !== "off";
    },
    // Muted mid-narration so a roll doesn't talk over the line reading it out.
    narrating() {
      return [...document.querySelectorAll("audio")].some((a) => !a.paused);
    },
  },
};
