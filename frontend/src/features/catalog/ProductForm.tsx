import { type FormEvent, useState } from "react";
import { fieldErrorsOf } from "@/api/client";
import {
  PRODUCT_STATUSES,
  type ProductIn,
  type ProductOut,
  type ProductStatus,
  type ProductUpdate,
} from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { InputField, SelectField, TextareaField } from "@/components/ui/Field";
import { Thumb } from "@/components/ui/Thumb";
import { minorToInput, parsePriceInput } from "@/lib/format";
import { isHttpUrl } from "@/lib/url";
import { AttributesEditor } from "./AttributesEditor";
import { useCreateProduct, useUpdateProduct } from "./api";
import { type AttributeRow, attributesFromRows, rowsFromAttributes, sameAttributes } from "./attributes";

interface FormState {
  name: string;
  description: string;
  price: string;
  imageUrl: string;
  status: ProductStatus;
  rows: AttributeRow[];
}

function initialState(product: ProductOut | null, currency: string): FormState {
  return {
    name: product?.name ?? "",
    description: product?.description ?? "",
    price: minorToInput(product?.price_minor ?? null, currency),
    imageUrl: product?.image_url ?? "",
    status: product?.status ?? "active",
    rows: product ? rowsFromAttributes(product.attributes) : [],
  };
}

type Built = { ok: true; body: ProductIn } | { ok: false; errors: Record<string, string> };

function buildBody(state: FormState, currency: string): Built {
  const errors: Record<string, string> = {};
  if (!state.name.trim()) errors.name = "Give the product a name";
  const price = parsePriceInput(state.price, currency);
  if (!price.ok) errors.price_minor = price.error;
  const imageUrl = state.imageUrl.trim();
  if (imageUrl && !isHttpUrl(imageUrl)) errors.image_url = "Use a full link starting with https://";
  const attributes = attributesFromRows(state.rows);
  if (!attributes.ok) errors.attributes = attributes.error;
  if (Object.keys(errors).length > 0 || !price.ok || !attributes.ok) return { ok: false, errors };
  return {
    ok: true,
    body: {
      name: state.name.trim(),
      description: state.description.trim() || null,
      attributes: attributes.value,
      price_minor: price.value,
      image_url: imageUrl || null,
      status: state.status,
    },
  };
}

/** Only send fields that changed. `null` means "clear this field". */
function diffProduct(product: ProductOut, body: ProductIn): ProductUpdate {
  const changes: ProductUpdate = {
    ...(body.name !== product.name && { name: body.name }),
    ...(body.description !== product.description && { description: body.description ?? null }),
    ...(body.price_minor !== product.price_minor && { price_minor: body.price_minor ?? null }),
    ...(body.image_url !== product.image_url && { image_url: body.image_url ?? null }),
    ...(body.status !== product.status && { status: body.status }),
  };
  const attributes = body.attributes ?? {};
  return sameAttributes(attributes, product.attributes) ? changes : { ...changes, attributes };
}

export function ProductForm({
  product,
  currency,
  onDone,
}: {
  product: ProductOut | null;
  currency: string;
  onDone: () => void;
}) {
  const [state, setState] = useState<FormState>(() => initialState(product, currency));
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const create = useCreateProduct();
  const update = useUpdateProduct();
  const mutation = product ? update : create;
  const errors = { ...fieldErrorsOf(mutation.error), ...clientErrors };
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setState((s) => ({ ...s, [key]: value }));

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const built = buildBody(state, currency);
    if (!built.ok) {
      setClientErrors(built.errors);
      return;
    }
    setClientErrors({});
    if (!product) {
      create.mutate(built.body, { onSuccess: onDone });
      return;
    }
    const changes = diffProduct(product, built.body);
    if (Object.keys(changes).length === 0) return onDone();
    update.mutate({ id: product.id, body: changes }, { onSuccess: onDone });
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {mutation.error ? <ErrorBanner error={mutation.error} /> : null}
      <InputField
        label="Name"
        required
        maxLength={200}
        value={state.name}
        onChange={(e) => set("name", e.target.value)}
        error={errors.name}
        placeholder="Linen wrap dress"
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <InputField
          label={`Price (${currency})`}
          inputMode="decimal"
          value={state.price}
          onChange={(e) => set("price", e.target.value)}
          error={errors.price_minor}
          placeholder="Leave blank if it varies"
        />
        <SelectField
          label="Status"
          value={state.status}
          onChange={(e) => set("status", e.target.value as ProductStatus)}
          error={errors.status}
          hint="Draft = not ready to sell yet"
        >
          {PRODUCT_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status === "active" ? "Active" : "Draft"}
            </option>
          ))}
        </SelectField>
      </div>
      <div className="flex items-end gap-3">
        <InputField
          label="Image URL"
          type="url"
          wrapperClassName="flex-1"
          value={state.imageUrl}
          onChange={(e) => set("imageUrl", e.target.value)}
          error={errors.image_url}
          placeholder="https://…"
        />
        <Thumb src={state.imageUrl} alt="Preview" className="mb-px size-10" />
      </div>
      <TextareaField
        label="Description"
        maxLength={5000}
        value={state.description}
        onChange={(e) => set("description", e.target.value)}
        error={errors.description}
        placeholder="What makes it special, sizing notes, delivery times…"
      />
      <AttributesEditor rows={state.rows} onChange={(rows) => set("rows", rows)} error={errors.attributes} />
      <div className="sticky bottom-0 -mx-6 -mb-5 flex justify-end gap-2 border-t border-border bg-surface-strong px-6 py-4">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={mutation.isPending}>
          {product ? "Save changes" : "Add product"}
        </Button>
      </div>
    </form>
  );
}
