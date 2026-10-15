import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { num, pct } from "../format";
import type { ProductReport, ReleaseStudy } from "../types";

const AXIS = { fontSize: 11, fill: "#667085" };
export const MIN_WEEKLY_REVIEWS = 20;
const GRID = "#eaecf0";

type TooltipRow = { name?: string | number; value?: unknown; color?: string };

function ChartTooltip({
  active,
  label,
  payload,
  formatLabel,
}: {
  active?: boolean;
  label?: string | number;
  payload?: TooltipRow[];
  formatLabel: (label: string) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <b>{formatLabel(String(label))}</b>
      {payload.map((row) => (
        <div key={String(row.name)}>
          <i style={{ background: row.color }} />
          {row.name}
          <span>
            {row.name === "不推荐率"
              ? pct(row.value as number)
              : num(row.value as number)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Weekly review volume (bars) and not-recommended rate (line). */
export function WeeklyTrend({ product }: { product: ProductReport }) {
  // A week with only a handful of reviews swings to 0% or 30%; leave its rate out.
  const data = product.weekly.map((w) => ({
    week: w.week,
    n: w.n,
    negative: w.negative,
    rate: w.n >= MIN_WEEKLY_REVIEWS ? w.rate : null,
  }));
  return (
    <>
      <div className="chart-legend">
        <span>
          <i style={{ background: "#d0d5dd" }} />
          评论数（左轴）
        </span>
        <span>
          <i className="line" style={{ background: "#2450c8" }} />
          不推荐率（右轴）
        </span>
      </div>
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 4, bottom: 0, left: 0 }}
          >
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="week"
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              tickFormatter={(w) => String(w).slice(5).replace("-", "/")}
              minTickGap={24}
            />
            <YAxis
              yAxisId="n"
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={36}
            />
            <YAxis
              yAxisId="rate"
              orientation="right"
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={40}
              tickFormatter={(v) => Math.round(v * 100) + "%"}
            />
            <Tooltip
              content={<ChartTooltip formatLabel={(w) => `${w} 起的一周`} />}
            />
            <Bar
              isAnimationActive={false}
              yAxisId="n"
              dataKey="n"
              name="评论数"
              fill="#d0d5dd"
              radius={[2, 2, 0, 0]}
              maxBarSize={22}
            />
            <Line
              isAnimationActive={false}
              yAxisId="rate"
              dataKey="rate"
              name="不推荐率"
              stroke="#2450c8"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

/** Daily recommended / not-recommended reviews in the 14 days either side of a release. */
export function ReleaseWindow({
  product,
  study,
}: {
  product: ProductReport;
  study: ReleaseStudy;
}) {
  const releaseDay = study.published_at.slice(0, 10);
  const start = study.window_before_start.slice(0, 10);
  const end = study.window_after_end.slice(0, 10);
  const data = product.daily
    .filter((d) => d.day >= start && d.day <= end)
    .map((d) => ({
      day: d.day,
      positive: (d.n ?? 0) - (d.negative ?? 0),
      negative: d.negative ?? 0,
    }));
  if (!data.length) return <p className="muted">这段时间没有采集到评论。</p>;
  return (
    <>
      <div className="chart-legend">
        <span>
          <i style={{ background: "#b2ccff" }} />
          推荐
        </span>
        <span>
          <i style={{ background: "#f04438" }} />
          不推荐
        </span>
        <span>
          {releaseDay < data[0].day
            ? `发布日 ${releaseDay} 早于已采集的评论`
            : "虚线为发布日"}
        </span>
      </div>
      <div className="chart small">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 16, right: 4, bottom: 0, left: 0 }}
          >
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="day"
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              tickFormatter={(d) => String(d).slice(5).replace("-", "/")}
              minTickGap={20}
            />
            <YAxis
              tick={AXIS}
              tickLine={false}
              axisLine={false}
              width={32}
              allowDecimals={false}
            />
            <Tooltip content={<ChartTooltip formatLabel={(d) => d} />} />
            <ReferenceLine
              x={releaseDay}
              stroke="#101828"
              strokeDasharray="4 3"
              label={{
                value: "发布",
                position: "top",
                fontSize: 11,
                fill: "#344054",
              }}
            />
            <Bar
              isAnimationActive={false}
              dataKey="positive"
              name="推荐"
              stackId="a"
              fill="#b2ccff"
              maxBarSize={18}
            />
            <Bar
              isAnimationActive={false}
              dataKey="negative"
              name="不推荐"
              stackId="a"
              fill="#f04438"
              maxBarSize={18}
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}
