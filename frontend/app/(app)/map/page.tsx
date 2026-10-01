"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  type Connection,
  Controls,
  type Edge,
  Handle,
  type Node,
  type NodeChange,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
import clsx from "clsx";
import { toPng } from "html-to-image";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useResolvedTheme } from "@/components/theme-toggle";
import { Button, Notice, PageHeader, StatusDot } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { deviceIp } from "@/lib/format";
import { NODE_H, NODE_W, type Point, autoLayout, groupBoxes, groupKey } from "@/lib/map-layout";
import type { Device, Group, MapData } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

type DeviceData = { device: Device; color: string; showIp: boolean };
type BoxData = { label: string; color: string; count: number };

function DeviceNode({ data }: NodeProps<Node<DeviceData>>) {
  const d = data.device;
  return (
    <div
      className={clsx(
        "flex items-center gap-2 rounded-lg border bg-card px-2.5",
        d.access === "pending" ? "border-dashed border-accent" : "border-line2",
        !d.online && "opacity-55",
      )}
      style={{ width: NODE_W, height: NODE_H }}
    >
      <Handle type="target" position={Position.Top} className="!size-2 !border-line2 !bg-card" />
      <span className="size-2.5 shrink-0 rounded-sm" style={{ background: data.color }} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-xs font-semibold text-text">{d.name}</span>
        {data.showIp && <span className="truncate font-mono text-[10.5px] text-faint">{deviceIp(d) ?? "—"}</span>}
      </span>
      <StatusDot online={d.online} />
      <Handle type="source" position={Position.Bottom} className="!size-2 !border-line2 !bg-card" />
    </div>
  );
}

function BoxNode({ data }: NodeProps<Node<BoxData>>) {
  return (
    <div className="h-full w-full rounded-xl border border-line" style={{ background: `${data.color}14` }}>
      <div className="flex items-center gap-2 px-3 pt-2 text-xs font-semibold text-text">
        <span className="size-2 rounded-sm" style={{ background: data.color }} />
        {data.label}
        <span className="ml-auto font-mono font-normal text-faint">{data.count}</span>
      </div>
    </div>
  );
}

const nodeTypes = { device: DeviceNode, box: BoxNode };
const PENDING_COLOR = "#E0A84E";
const NEUTRAL_COLOR = "#9AA3A8";

export default function MapPage() {
  const theme = useResolvedTheme();
  const devicesRes = useResource<Device[]>("/devices", { refreshMs: 60_000 });
  const groupsRes = useResource<Group[]>("/groups");
  const mapRes = useResource<MapData>("/map");
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [showIp, setShowIp] = useState(true);
  const [linkKind, setLinkKind] = useState<"wired" | "wifi">("wifi");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string }>();
  const groups = useMemo(() => groupsRes.data ?? [], [groupsRes.data]);
  const devices = useMemo(() => (devicesRes.data ?? []).filter((d) => d.access !== "blocked"), [devicesRes.data]);

  useEffect(() => {
    if (!devicesRes.data || !groupsRes.data || !mapRes.data) return;
    const saved = Object.fromEntries(mapRes.data.positions.map((p) => [p.device_id, { x: p.x, y: p.y }]));
    const auto = autoLayout(devices, groups);
    setPositions((current) => ({ ...auto, ...saved, ...current }));
  }, [devicesRes.data, groupsRes.data, mapRes.data, devices, groups]);

  const colorOf = useCallback(
    (d: Device) => (d.access === "pending" ? PENDING_COLOR : groups.find((g) => g.id === d.group_id)?.color ?? NEUTRAL_COLOR),
    [groups],
  );
  const boxLabel = useCallback(
    (key: string) => (key === "pending" ? "Quarantine" : key === "ungrouped" ? "Unassigned" : groups.find((g) => `g${g.id}` === key)?.name ?? key),
    [groups],
  );
  const boxColor = useCallback(
    (key: string) => (key === "pending" ? PENDING_COLOR : groups.find((g) => `g${g.id}` === key)?.color ?? NEUTRAL_COLOR),
    [groups],
  );

  const nodes = useMemo<Node[]>(() => {
    const boxes = groupBoxes(devices, positions).map<Node<BoxData>>((box) => ({
      id: `box:${box.key}`,
      type: "box",
      position: { x: box.x, y: box.y },
      data: { label: boxLabel(box.key), color: boxColor(box.key), count: devices.filter((d) => groupKey(d) === box.key).length },
      style: { width: box.w, height: box.h },
      draggable: false,
      selectable: false,
      connectable: false,
      zIndex: -1,
    }));
    const deviceNodes = devices
      .filter((d) => positions[d.id])
      .map<Node<DeviceData>>((d) => ({ id: d.id, type: "device", position: positions[d.id], data: { device: d, color: colorOf(d), showIp } }));
    return [...boxes, ...deviceNodes];
  }, [devices, positions, showIp, colorOf, boxLabel, boxColor]);

  const edges = useMemo<Edge[]>(
    () =>
      (mapRes.data?.links ?? []).map((link) => ({
        id: `link:${link.id}`,
        source: link.source_id,
        target: link.target_id,
        label: link.label ?? undefined,
        style: {
          stroke: link.kind === "wifi" ? "var(--ok)" : "var(--muted)",
          strokeWidth: 1.6,
          strokeDasharray: link.kind === "wifi" ? "6 4" : undefined,
        },
      })),
    [mapRes.data],
  );

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setPositions((current) => {
      let next = current;
      for (const change of changes) {
        if (change.type === "position" && change.position && !change.id.startsWith("box:")) {
          next = { ...next, [change.id]: change.position };
        }
      }
      return next;
    });
  }, []);

  const onNodeDragStop = useCallback(async (_: unknown, node: Node) => {
    if (node.id.startsWith("box:")) return;
    try {
      await api.put("/map/positions", [{ device_id: node.id, x: node.position.x, y: node.position.y }]);
    } catch (err) {
      setMessage({ tone: "error", text: errorText(err) });
    }
  }, []);

  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target || connection.source.startsWith("box:") || connection.target.startsWith("box:")) return;
      try {
        await api.post("/map/links", { source_id: connection.source, target_id: connection.target, kind: linkKind });
        await mapRes.reload();
      } catch (err) {
        setMessage({ tone: "error", text: errorText(err) });
      }
    },
    [linkKind, mapRes],
  );

  const onEdgeClick = useCallback(
    async (_: unknown, edge: Edge) => {
      if (!window.confirm("Remove this link?")) return;
      try {
        await api.del(`/map/links/${edge.id.replace("link:", "")}`);
        await mapRes.reload();
      } catch (err) {
        setMessage({ tone: "error", text: errorText(err) });
      }
    },
    [mapRes],
  );

  async function arrange() {
    const auto = autoLayout(devices, groups);
    setPositions(auto);
    try {
      await api.put("/map/positions", Object.entries(auto).map(([device_id, p]) => ({ device_id, x: p.x, y: p.y })));
      setMessage({ tone: "success", text: "Layout saved." });
    } catch (err) {
      setMessage({ tone: "error", text: errorText(err) });
    }
  }

  async function exportPng() {
    const element = document.querySelector<HTMLElement>(".react-flow");
    if (!element) return;
    const url = await toPng(element, { backgroundColor: getComputedStyle(document.body).backgroundColor });
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "janus-map.png";
    anchor.click();
  }

  const online = devices.filter((d) => d.online).length;
  const pending = devices.filter((d) => d.access === "pending").length;

  return (
    <>
      <PageHeader
        title="Network map"
        subtitle="drag to arrange · drag from the bottom dot of one device to another to draw an uplink · click a link to remove it"
        actions={
          <>
            <div role="group" aria-label="New link type" className="inline-flex gap-0.5 rounded-lg border border-line bg-row p-1">
              {(["wifi", "wired"] as const).map((kind) => (
                <button
                  key={kind}
                  type="button"
                  aria-pressed={linkKind === kind}
                  onClick={() => setLinkKind(kind)}
                  className={clsx("h-9 rounded-md px-3 text-sm font-medium", linkKind === kind ? "bg-card text-text shadow-sm" : "text-muted")}
                >
                  {kind === "wifi" ? "Wi-Fi link" : "Wired link"}
                </button>
              ))}
            </div>
            <Button aria-pressed={showIp} onClick={() => setShowIp((v) => !v)}>
              {showIp ? "Hide IPs" : "Show IPs"}
            </Button>
            <Button onClick={() => void exportPng()}>Export PNG</Button>
            <Button variant="primary" onClick={() => void arrange()}>
              Auto layout
            </Button>
          </>
        }
      />
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
      {(devicesRes.error || mapRes.error) && <Notice tone="error">{devicesRes.error ?? mapRes.error}</Notice>}
      <div className="relative h-[calc(100dvh-230px)] min-h-[520px] overflow-hidden rounded-2xl border border-line bg-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onNodeDragStop={onNodeDragStop}
          onConnect={onConnect}
          onEdgeClick={onEdgeClick}
          colorMode={theme}
          fitView
          minZoom={0.15}
        >
          <Background gap={18} color="var(--dotgrid)" />
          <Controls showInteractive={false} />
        </ReactFlow>
        <div className="pointer-events-none absolute right-4 top-4 flex flex-col gap-2 rounded-xl border border-line bg-card p-3 text-xs text-muted">
          <span className="flex items-center gap-2">
            <span className="w-6 border-t-[1.5px] border-muted" />
            Wired
          </span>
          <span className="flex items-center gap-2">
            <span className="w-6 border-t-[1.5px] border-dashed border-ok" />
            Wi-Fi
          </span>
          <span className="flex items-center gap-2">
            <span className="size-3.5 rounded border-[1.5px] border-dashed border-accent" />
            Pending
          </span>
          <span className="mt-1 font-mono">
            {devices.length} devices · {online} online · {pending} pending
          </span>
        </div>
      </div>
    </>
  );
}
