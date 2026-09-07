// Dice thrown across the page: real physics, then relabelled to the value Python rolled.
import DiceBox from "dice-box-threejs";

const SOUND_KEY = "aidm.dice.sound";
const REST_MS = 2500;
const FADE_MS = 500;

export default {
  template: "<div></div>",
  props: { look: Object, assets: String },
  data() {
    return { clearing: null };
  },
  created() {
    // Outside `data()`: a reactive proxy around the box breaks Three.js's own objects.
    this.box = null;
  },
  async mounted() {
    this.$emit("sound", this.soundOn());
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const probe = document.createElement("canvas");
    if (!probe.getContext("webgl2") && !probe.getContext("webgl")) return;
    const box = new DiceBox("#" + this.$el.id, {
      assetPath: this.assets,
      sounds: true,
      theme_customColorset: {
        name: "aidm",
        foreground: this.look.ink,
        background: this.look.body,
        outline: this.look.glow,
        texture: "none",
        material: "none",
      },
      theme_surface: "green-felt",
      shadows: false,
      strength: 1.5,
      onRollComplete: () => this.rested(),
    });
    try {
      await box.initialize();
      this.box = box;
    } catch (error) {
      console.error(error);
    }
  },
  unmounted() {
    clearTimeout(this.clearing);
    this.box?.clearDice();
    this.box = null;
  },
  methods: {
    toss(dice) {
      if (!this.box) return;
      clearTimeout(this.clearing);
      this.$el.style.opacity = "";
      // Muted mid-narration so a roll doesn't talk over the line reading it out.
      this.box.sounds = this.soundOn() && !this.narrating();
      this.box.roll(notation(dice));
    },
    toggleSound() {
      const on = !this.soundOn();
      localStorage.setItem(SOUND_KEY, on ? "on" : "off");
      this.$emit("sound", on);
    },
    soundOn() {
      return localStorage.getItem(SOUND_KEY) !== "off";
    },
    rested() {
      this.clearing = setTimeout(() => {
        this.$el.style.opacity = "0";
        this.clearing = setTimeout(() => {
          this.box?.clearDice();
          this.$el.style.opacity = "";
        }, FADE_MS);
      }, REST_MS);
    },
    narrating() {
      return [...document.querySelectorAll("audio")].some((a) => !a.paused);
    },
  },
};

// The library's notation reads one "@" tail of prescribed values, in spawn order; same-type
// sets merge, so dice of the same faces must share one group.
function notation(dice) {
  const groups = [];
  for (const die of dice) {
    const group = groups.find((g) => g[0].faces === die.faces);
    if (group) group.push(die);
    else groups.push([die]);
  }
  const sets = groups.map((g) => `${g.length}d${g[0].faces}`).join("+");
  const values = groups.flat().map((d) => d.value).join(",");
  return `${sets}@${values}`;
}
