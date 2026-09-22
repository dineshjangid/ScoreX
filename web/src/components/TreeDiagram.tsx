import type { TreeNode } from "../api";

interface Props {
  nodes: Record<string, TreeNode>;
  rootId: string;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const BOX_W = 150;
const BOX_H = 64;
const H_GAP = 24;
const V_GAP = 46;

function layout(nodes: Record<string, TreeNode>, rootId: string): Record<string, number> {
  let next = 0;
  const xOf: Record<string, number> = {};
  function visit(id: string): number {
    const node = nodes[id];
    if (!node || node.children.length === 0) {
      xOf[id] = next++;
      return xOf[id];
    }
    const xs = node.children.map(visit);
    xOf[id] = xs.reduce((a, b) => a + b, 0) / xs.length;
    return xOf[id];
  }
  visit(rootId);
  return xOf;
}

function badRateColor(pct: number): string {
  const t = Math.min(pct / 40, 1);
  const hue = 140 - t * 140; // green (safe) -> red (risky)
  return `hsl(${hue}, 60%, 42%)`;
}

function truncate(text: string, max = 26): string {
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

export default function TreeDiagram({ nodes, rootId, selectedId, onSelect }: Props) {
  const ids = Object.keys(nodes);
  const xOf = layout(nodes, rootId);
  const maxX = Math.max(...ids.map((id) => xOf[id]), 0);
  const maxDepth = Math.max(...ids.map((id) => nodes[id].depth), 0);
  const width = (maxX + 1) * (BOX_W + H_GAP) + H_GAP;
  const height = (maxDepth + 1) * (BOX_H + V_GAP) + V_GAP;

  const px = (id: string) => xOf[id] * (BOX_W + H_GAP) + H_GAP;
  const py = (id: string) => nodes[id].depth * (BOX_H + V_GAP) + V_GAP / 2;

  return (
    <div className="tree-diagram-scroll">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="decision tree">
        {ids.flatMap((id) =>
          nodes[id].children.map((childId) => (
            <line
              key={`${id}-${childId}`}
              x1={px(id) + BOX_W / 2}
              y1={py(id) + BOX_H}
              x2={px(childId) + BOX_W / 2}
              y2={py(childId)}
              stroke="var(--border)"
              strokeWidth={1.5}
            />
          ))
        )}
        {ids.map((id) => {
          const node = nodes[id];
          const x = px(id);
          const y = py(id);
          const selected = id === selectedId;
          const label = node.branch_rule ? truncate(node.branch_description) : "All records";
          return (
            <g key={id} onClick={() => onSelect(id)} style={{ cursor: "pointer" }}>
              <rect
                x={x}
                y={y}
                width={BOX_W}
                height={BOX_H}
                rx={7}
                fill={badRateColor(node.bad_rate_pct)}
                opacity={selected ? 1 : 0.82}
                stroke={selected ? "var(--accent)" : "var(--border)"}
                strokeWidth={selected ? 3 : 1}
              >
                <title>{node.branch_rule ? node.branch_description : "All records"}</title>
              </rect>
              <text x={x + BOX_W / 2} y={y + 16} textAnchor="middle" fontSize="9.5" fill="white">
                {label}
              </text>
              <text x={x + BOX_W / 2} y={y + 34} textAnchor="middle" fontSize="12" fontWeight="600" fill="white">
                N={node.n_total}
              </text>
              <text x={x + BOX_W / 2} y={y + 50} textAnchor="middle" fontSize="10.5" fill="white">
                bad {node.bad_rate_pct}%
              </text>
              {node.is_leaf && node.policy && (
                <text x={x + BOX_W / 2} y={y + 62} textAnchor="middle" fontSize="9.5" fill="white" fontStyle="italic">
                  {node.policy}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
