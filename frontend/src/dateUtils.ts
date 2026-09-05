const MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const MONTH_START_DAY: number[] = (() => {
  const starts: number[] = [];
  let acc = 0;
  for (const len of MONTH_LENGTHS) {
    starts.push(acc);
    acc += len;
  }
  return starts;
})();

export function dayToMonthLabel(day: number): string {
  let monthIdx = 0;
  for (let i = 0; i < MONTH_START_DAY.length; i++) {
    if (day >= MONTH_START_DAY[i]) monthIdx = i;
  }
  return MONTH_NAMES[monthIdx];
}

export function isFirstOfMonth(day: number): boolean {
  return MONTH_START_DAY.includes(day);
}

export const MONTH_TICKS = MONTH_START_DAY;
