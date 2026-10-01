import { api } from "@/lib/api";
import type { Device } from "@/lib/types";

export function deleteConfirmText(device: Pick<Device, "name">): string {
  return `Delete ${device.name}? Janus forgets it and drops its IP reservation. If it is still connected it will show up again as a new device waiting for approval.`;
}

export async function deleteDevice(device: Pick<Device, "id" | "name">): Promise<boolean> {
  if (!window.confirm(deleteConfirmText(device))) return false;
  await api.del(`/devices/${device.id}`);
  return true;
}
