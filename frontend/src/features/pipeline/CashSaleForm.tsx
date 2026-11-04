import { Banknote } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { InputField } from "@/components/ui/Field";
import { minorToInput, parsePriceInput } from "@/lib/format";

/**
 * "Record a cash sale": sets the deal value (in the business currency's minor units)
 * when marking a deal won that has no amount, or no product to price it from.
 */
export function CashSaleForm({
  currency,
  initialMinor,
  marking,
  pending,
  onSubmit,
  onSkip,
  onCancel,
}: {
  currency: string;
  initialMinor: number | null;
  /** true: this also moves the deal to Won; false: only records the amount on a won deal. */
  marking: boolean;
  pending: boolean;
  onSubmit: (amountMinor: number) => void;
  onSkip?: () => void;
  onCancel?: () => void;
}) {
  const [value, setValue] = useState(() => minorToInput(initialMinor, currency));
  const [error, setError] = useState<string | undefined>();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const parsed = parsePriceInput(value, currency);
    if (!parsed.ok) return setError(parsed.error);
    if (parsed.value === null) return setError("Enter what the shopper paid");
    setError(undefined);
    onSubmit(parsed.value);
  };

  return (
    <form
      onSubmit={submit}
      noValidate
      className="space-y-3 rounded-xl bg-emerald-500/5 p-4 ring-1 ring-emerald-500/30 animate-enter"
    >
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Banknote className="size-4 text-success" aria-hidden />
        Record a cash sale
      </p>
      <InputField
        label={`Amount paid (${currency})`}
        inputMode="decimal"
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        error={error}
        hint="Paid outside the checkout link, e.g. cash on delivery."
      />
      <div className="flex flex-wrap justify-end gap-2">
        {onCancel ? (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        {onSkip ? (
          <Button variant="secondary" size="sm" onClick={onSkip}>
            Mark won without an amount
          </Button>
        ) : null}
        <Button type="submit" size="sm" loading={pending}>
          {marking ? "Mark as won" : "Save amount"}
        </Button>
      </div>
    </form>
  );
}
