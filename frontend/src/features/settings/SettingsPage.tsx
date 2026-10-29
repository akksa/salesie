import { CircleCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { fieldErrorsOf } from "@/api/client";
import type { BusinessOut, BusinessUpdate } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { InputField, TextareaField } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { formatMoney } from "@/lib/format";
import { useBusiness, useUpdateBusiness } from "./api";

interface FormState {
  name: string;
  currency: string;
  ig: string;
  fb: string;
  wa: string;
  notes: string;
}

function toState(business: BusinessOut): FormState {
  return {
    name: business.name,
    currency: business.currency,
    ig: business.ig_account_id ?? "",
    fb: business.fb_page_id ?? "",
    wa: business.wa_phone_number_id ?? "",
    notes: business.sales_notes ?? "",
  };
}

function validate(state: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!state.name.trim()) errors.name = "Your business needs a name";
  if (!/^[A-Z]{3}$/.test(state.currency.trim()))
    errors.currency = "Use a 3-letter ISO code like USD, EUR or INR";
  return errors;
}

/** Only changed fields are sent; a cleared account id is sent as null. */
function diffBusiness(business: BusinessOut, state: FormState): BusinessUpdate {
  const optional = (value: string) => value.trim() || null;
  return {
    ...(state.name.trim() !== business.name && { name: state.name.trim() }),
    ...(state.currency.trim() !== business.currency && { currency: state.currency.trim() }),
    ...(optional(state.ig) !== business.ig_account_id && { ig_account_id: optional(state.ig) }),
    ...(optional(state.fb) !== business.fb_page_id && { fb_page_id: optional(state.fb) }),
    ...(optional(state.wa) !== business.wa_phone_number_id && { wa_phone_number_id: optional(state.wa) }),
    ...(optional(state.notes) !== business.sales_notes && { sales_notes: optional(state.notes) }),
  };
}

function BusinessForm({ business }: { business: BusinessOut }) {
  const [state, setState] = useState<FormState>(() => toState(business));
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const update = useUpdateBusiness();
  const errors = { ...fieldErrorsOf(update.error), ...clientErrors };
  const set = (key: keyof FormState, value: string) => {
    update.reset();
    setState((s) => ({ ...s, [key]: value }));
  };
  const changes = diffBusiness(business, state);
  const dirty = Object.keys(changes).length > 0;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const found = validate(state);
    setClientErrors(found);
    if (Object.keys(found).length === 0 && dirty) update.mutate(changes);
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4 p-5">
      {update.error ? <ErrorBanner error={update.error} /> : null}
      <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
        <InputField
          label="Business name"
          required
          maxLength={200}
          value={state.name}
          onChange={(e) => set("name", e.target.value)}
          error={errors.name}
        />
        <InputField
          label="Currency"
          required
          maxLength={3}
          value={state.currency}
          onChange={(e) => set("currency", e.target.value.toUpperCase())}
          error={errors.currency}
          hint={errors.currency ? undefined : `e.g. ${formatMoney(129900, state.currency) ?? ""}`}
          className="font-mono uppercase"
        />
      </div>
      <fieldset className="grid gap-4 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-medium">Meta account ids</legend>
        <InputField
          label="Instagram account id"
          maxLength={64}
          value={state.ig}
          onChange={(e) => set("ig", e.target.value)}
          error={errors.ig_account_id}
          className="font-mono"
        />
        <InputField
          label="Facebook Page id"
          maxLength={64}
          value={state.fb}
          onChange={(e) => set("fb", e.target.value)}
          error={errors.fb_page_id}
          className="font-mono"
        />
        <InputField
          label="WhatsApp phone number id"
          maxLength={64}
          value={state.wa}
          onChange={(e) => set("wa", e.target.value)}
          error={errors.wa_phone_number_id}
          className="font-mono"
        />
      </fieldset>
      <TextareaField
        label="Shop notes for the agent"
        maxLength={4000}
        rows={5}
        value={state.notes}
        onChange={(e) => set("notes", e.target.value)}
        error={errors.sales_notes}
        hint={`The agent can quote these; anything else it hands to you. ${state.notes.length}/4000`}
        placeholder={
          "Shipping: 3-5 days nationwide, free over 2,000.\nReturns: 7 days, unworn with tags.\nPayment: card via our checkout link, or cash on delivery in the city."
        }
      />
      <div className="flex items-center justify-end gap-3">
        {update.isSuccess && !dirty ? (
          <span
            className="inline-flex items-center gap-1.5 text-sm font-medium text-success animate-enter"
            role="status"
          >
            <CircleCheck className="size-4" aria-hidden /> Saved
          </span>
        ) : null}
        <Button type="submit" loading={update.isPending} disabled={!dirty}>
          Save changes
        </Button>
      </div>
    </form>
  );
}

export function SettingsPage() {
  const business = useBusiness();
  return (
    <>
      <PageHeader
        eyebrow="Settings"
        title="Your business"
        description="Name, currency, the Meta accounts Salesie listens to, and what the agent may tell shoppers."
      />
      {business.isError ? (
        <ErrorBanner error={business.error} onRetry={() => business.refetch()} className="mb-4" />
      ) : null}
      <Card>
        <CardHeader
          title="Business profile"
          description="Prices across the dashboard use this currency. Changing it does not convert existing prices."
        />
        {business.isPending ? <SkeletonRows rows={2} /> : null}
        {business.data ? <BusinessForm key={business.data.id} business={business.data} /> : null}
      </Card>
    </>
  );
}
