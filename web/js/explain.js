// The explanation that sits beside the phone (or behind the info button on a
// narrow screen): how to read the colours, what ran offline to produce the
// screen in view, and the pipeline. The explanatory vocabulary lives here and
// on the About page; inside the phone the app's own words are used.
import { h } from './dom.js';
import { pipelineDiagram } from './about.js';

const SCREENS = {
  home: ['The people', [
    'Four synthetic people, each with about half a year of simulated health data. The figures on each card are the last full week of that person’s data, picked and formatted by Python.',
    'Choose a person, then one of their goals, to open the app as that person.']],
  person: ['Choosing a goal', [
    'Each goal was taken through the real onboarding interview and plan builder offline. Entering one opens the app as this person with that goal, starting where a new user starts.']],
  welcome: ['First run', [
    'This is the onboarding interview that produced the plan, replayed. The questions were asked by the model; the person’s answers are scripted, because the person is synthetic.',
    'The cards inside the transcript were computed by Python from the recorded data. The first week was drafted by the plan model and passed Python’s checks before it was offered; anything the checks refused would be listed on the card.',
    'Accept does not write anything here. It opens the app on the plan that was accepted offline.']],
  today: ['Today', [
    'Python read the plan for this day, computed readiness from recent heart-rate variability and resting heart rate, and graded the day before against what was planned. No model computes anything on this screen.',
    'A section that cannot be grounded says so in a muted card instead of guessing: that is a refusal, and it is the system working.',
    'When a brief is shown below the day, it is the only text on this screen that a model wrote. Every number in it was checked against the facts Python published for that brief, and a brief that failed the check is shown as Python’s own text instead.']],
  week: ['Week', [
    'The first week of the plan, day by day, as it was accepted during onboarding. Only this week is written out session by session.',
    'The long plan below it carries words only: for each later week a phase, a key session and one sentence of intent written by the plan model and checked to state no training amount. The position, the dates and the labels are Python’s.']],
  day: ['A day of the week', [
    'The same view as Today, for the day you opened. For a day after the data ends only the planned session is shown; there is nothing yet to measure.']],
  chat: ['Chat', [
    'Each question was asked offline. Python computed a fact set for it, the model wrote a sentence around those facts, and a verification gate checked every figure in the draft against the fact set before it was kept.',
    'An answer that failed the gate is a fallback: Python’s own template text, shown under the label “Answer withheld”. The line under each answer is the count of figures the gate traced, and Sources lists what Python computed and where each value came from.',
    'The short wait is for show. Nothing is being generated.']],
  reports: ['Reports', [
    'Weekly series computed by Python from the simulated data. The sentence under each chart was also composed in Python from the points shown, which is why it is not in serif.']],
  briefs: ['Daily briefs', [
    'Each brief has two parts. The facts block is written by Python from the plan and the data: its lines and its numbers are not a model’s. The narration, the paragraph at the end, is the one part the model wrote, and it is set in serif.',
    'A figure in the narration wears the figure colour when it matches one of the facts Python published. The line under the brief counts the figures the check traced, and Sources lists the facts the brief was built from.',
    'If the model’s paragraph failed the check, Python’s own fixed sentence closes the brief instead and says so.']],
  about: ['About', ['How the demo was made, which models wrote the wording, and what it leaves out.']],
  missing: ['Not found', ['There is nothing at this address.']],
};

function legend() {
  return h('dl', { class: 'legend' },
    h('div', null, h('dt', null, h('span', { class: 'fig' }, '59/100')), h('dd', null, 'Figure colour: computed by Python.')),
    h('div', null, h('dt', null, h('span', { class: 'serif' }, 'Aa')), h('dd', null, 'Serif: written by the model.')),
    h('div', null, h('dt', null, h('span', { class: 'muted' }, 'Aa')), h('dd', null, 'Muted: a deliberate refusal, not an error.')));
}

let diagram = null;

/** Fill the panel for the screen in view. The diagram is built once. */
export function renderExplain(body, screen) {
  const [title, paragraphs] = SCREENS[screen] ?? SCREENS.missing;
  diagram = diagram ?? pipelineDiagram();
  body.replaceChildren(
    h('section', { 'aria-labelledby': 'ex-screen' },
      h('h3', { id: 'ex-screen' }, `This screen: ${title}`),
      paragraphs.map((text) => h('p', null, text))),
    h('section', { 'aria-labelledby': 'ex-legend' },
      h('h3', { id: 'ex-legend' }, 'How to read it'), legend()),
    h('section', { 'aria-labelledby': 'ex-pipe' },
      h('h3', { id: 'ex-pipe' }, 'What ran offline'),
      h('p', null, 'Everything here was generated in advance and frozen. This site only serves the result.'),
      // The About page carries the diagram itself.
      screen === 'about' ? null : [diagram, h('p', null, h('a', { href: '#/about' }, 'More about how this demo works'))]));
}
