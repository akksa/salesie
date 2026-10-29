import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { type AttributeRow, newRowId } from "./attributes";

const INPUT =
  "h-9 min-w-0 rounded-lg border border-border bg-surface-strong px-2.5 text-sm text-fg placeholder:text-fg-subtle " +
  "transition-[border-color,box-shadow] duration-200 hover:border-border-strong focus:border-ring focus:outline-none focus:ring-4 focus:ring-ring/15";

export function AttributesEditor({
  rows,
  onChange,
  error,
}: {
  rows: AttributeRow[];
  onChange: (rows: AttributeRow[]) => void;
  error?: string | undefined;
}) {
  const update = (rowId: string, patch: Partial<AttributeRow>) =>
    onChange(rows.map((row) => (row.rowId === rowId ? { ...row, ...patch } : row)));
  const remove = (rowId: string) => onChange(rows.filter((row) => row.rowId !== rowId));
  const add = () => onChange([...rows, { rowId: newRowId(), key: "", value: "" }]);

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1.5 text-sm font-medium">Attributes</legend>
      <p className="-mt-1 mb-1 text-xs text-fg-subtle">
        Size, colour, material… the AI agent uses these to answer questions.
      </p>
      {rows.map((row, index) => (
        <div key={row.rowId} className="flex items-center gap-2 animate-enter">
          <input
            aria-label={`Attribute ${index + 1} name`}
            placeholder="e.g. colour"
            value={row.key}
            onChange={(e) => update(row.rowId, { key: e.target.value })}
            className={cn(INPUT, "w-2/5")}
          />
          <input
            aria-label={`Attribute ${index + 1} value`}
            placeholder="e.g. sage green"
            value={row.value}
            onChange={(e) => update(row.rowId, { value: e.target.value })}
            className={cn(INPUT, "flex-1")}
          />
          <button
            type="button"
            onClick={() => remove(row.rowId)}
            aria-label={`Remove attribute ${row.key || index + 1}`}
            className="grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg text-fg-subtle transition-colors hover:bg-danger-bg hover:text-danger"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      ))}
      <div>
        <Button variant="ghost" size="sm" onClick={add} icon={<Plus className="size-4" aria-hidden />}>
          Add attribute
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-xs font-medium text-danger">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
