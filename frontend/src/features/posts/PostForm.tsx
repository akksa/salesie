import { type FormEvent, useState } from "react";
import { fieldErrorsOf } from "@/api/client";
import type { PostIn, ProductOut } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { InputField, SelectField, TextareaField } from "@/components/ui/Field";
import { Thumb } from "@/components/ui/Thumb";
import { isHttpUrl } from "@/lib/url";
import { useCreatePost } from "./api";
import { ProductOptions, toProductId } from "./ProductSelect";

interface FormState {
  externalId: string;
  caption: string;
  imageUrl: string;
  permalink: string;
  productId: string;
}

const EMPTY: FormState = { externalId: "", caption: "", imageUrl: "", permalink: "", productId: "" };

function validate(state: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!state.externalId.trim()) errors.external_id = "Paste the Instagram media id";
  if (state.imageUrl.trim() && !isHttpUrl(state.imageUrl.trim()))
    errors.image_url = "Use a full https:// link";
  if (state.permalink.trim() && !isHttpUrl(state.permalink.trim()))
    errors.permalink = "Use a full https:// link";
  return errors;
}

function toBody(state: FormState): PostIn {
  return {
    channel: "instagram",
    external_id: state.externalId.trim(),
    caption: state.caption.trim() || null,
    image_url: state.imageUrl.trim() || null,
    permalink: state.permalink.trim() || null,
    product_id: toProductId(state.productId),
  };
}

export function PostForm({ products, onDone }: { products: ProductOut[]; onDone: () => void }) {
  const [state, setState] = useState<FormState>(EMPTY);
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const create = useCreatePost();
  const errors = { ...fieldErrorsOf(create.error), ...clientErrors };
  const set = (key: keyof FormState, value: string) => setState((s) => ({ ...s, [key]: value }));

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const found = validate(state);
    setClientErrors(found);
    if (Object.keys(found).length === 0) create.mutate(toBody(state), { onSuccess: onDone });
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {create.error ? <ErrorBanner error={create.error} /> : null}
      <InputField
        label="Instagram media id"
        required
        maxLength={128}
        value={state.externalId}
        onChange={(e) => set("externalId", e.target.value)}
        error={errors.external_id}
        hint="The id Meta sends in comment webhooks, e.g. 17895695668004550"
        className="font-mono"
      />
      <SelectField
        label="Linked product"
        value={state.productId}
        onChange={(e) => set("productId", e.target.value)}
        error={errors.product_id}
        hint="Leads from this post are attached to this product"
      >
        <ProductOptions products={products} emptyLabel="No product yet" />
      </SelectField>
      <TextareaField
        label="Caption"
        maxLength={5000}
        value={state.caption}
        onChange={(e) => set("caption", e.target.value)}
        error={errors.caption}
        placeholder="New drop: linen wrap dress, DM to order"
      />
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
      <InputField
        label="Permalink"
        type="url"
        value={state.permalink}
        onChange={(e) => set("permalink", e.target.value)}
        error={errors.permalink}
        placeholder="https://www.instagram.com/p/…"
      />
      <div className="sticky bottom-0 -mx-6 -mb-5 flex justify-end gap-2 border-t border-border bg-surface-strong px-6 py-4">
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={create.isPending}>
          Register post
        </Button>
      </div>
    </form>
  );
}
