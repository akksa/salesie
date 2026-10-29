import { useEffect, useRef, useState } from "react";

/**
 * Returns ids that appeared after the first successful load, so freshly-arrived
 * rows (e.g. from the simulator) can be highlighted. The initial batch is never "new".
 */
export function useNewIds(ids: number[] | undefined): ReadonlySet<number> {
  const seen = useRef<ReadonlySet<number> | null>(null);
  const [fresh, setFresh] = useState<ReadonlySet<number>>(new Set());
  const signature = ids?.join(",");

  // biome-ignore lint/correctness/useExhaustiveDependencies: `signature` captures the ids content
  useEffect(() => {
    if (!ids) return;
    if (seen.current === null) {
      seen.current = new Set(ids);
      return;
    }
    const previous = seen.current;
    const arrived = ids.filter((id) => !previous.has(id));
    seen.current = new Set([...previous, ...ids]);
    if (arrived.length > 0) setFresh(new Set(arrived));
  }, [signature]);

  return fresh;
}
