// A mic button that dictates into another element's draft via the browser's own SpeechRecognition.
export default {
  template: `
    <div :hidden="!supported">
      <q-btn round flat :icon="recording ? 'stop' : 'mic'" :color="recording ? 'negative' : undefined"
        :class="{ 'game-dictating': recording }" aria-label="Dictate" @click="press"></q-btn>
      <div class="text-xs opacity-70">{{ interim }}</div>
    </div>
  `,
  props: { target: String },
  data() {
    return { recognizer: null, interim: "", finals: [], caret: 0, recording: false, finalising: false, timer: null };
  },
  computed: {
    supported() {
      return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
    },
  },
  methods: {
    press() {
      if (!this.recording) {
        this.start();
        return;
      }
      if (this.finalising) return;
      this.finalising = true;
      this.recognizer.stop();
    },
    start() {
      const box = document.getElementById(this.target)?.querySelector("textarea");
      this.caret = box ? box.selectionStart : 0;
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognizer = new Recognition();
      recognizer.continuous = true;
      recognizer.interimResults = true;
      recognizer.lang = navigator.language;
      recognizer.onresult = (event) => this.onresult(event);
      recognizer.onend = () => this.finish();
      recognizer.onerror = (event) => this.onerror(event);
      this.finals = [];
      this.interim = "";
      this.recording = true;
      this.finalising = false;
      this.recognizer = recognizer;
      recognizer.start();
      this.timer = setTimeout(() => recognizer.stop(), 60000);
    },
    onresult(event) {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) this.finals.push(result[0].transcript.trim());
        else interim += result[0].transcript;
      }
      this.interim = interim;
    },
    finish() {
      if (!this.recording) return;
      clearTimeout(this.timer);
      const text = this.finals.join(" ").trim();
      const caret = this.caret;
      this.recognizer = null;
      this.recording = false;
      this.finalising = false;
      this.interim = "";
      this.finals = [];
      if (text) this.$emit("dictated", { text, caret });
    },
    onerror(event) {
      clearTimeout(this.timer);
      this.recognizer = null;
      this.recording = false;
      this.finalising = false;
      this.interim = "";
      this.finals = [];
      this.$emit("failed", event.error);
    },
  },
  unmounted() {
    clearTimeout(this.timer);
    if (this.recognizer) this.recognizer.abort();
  },
};
