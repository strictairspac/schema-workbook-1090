import {RUN_STATES,RETIRE_STATES} from '../../constants/enums.js';
import {esc} from '../../utils/html.js';
const LABELS={...RUN_STATES,...RETIRE_STATES};
export const badge=value=>`<span class="badge ${esc(value)}">${esc(LABELS[value]||value)}</span>`;
