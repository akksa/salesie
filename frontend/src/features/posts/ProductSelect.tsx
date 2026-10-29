import type { ProductOut } from "@/api/types";

/** <option>s for picking a catalog product; drafts are labelled so the owner notices. */
export function ProductOptions({ products, emptyLabel }: { products: ProductOut[]; emptyLabel: string }) {
  return (
    <>
      <option value="">{emptyLabel}</option>
      {products.map((product) => (
        <option key={product.id} value={product.id}>
          {product.name}
          {product.status === "draft" ? " (draft)" : ""}
        </option>
      ))}
    </>
  );
}

export function toProductId(value: string): number | null {
  return value === "" ? null : Number(value);
}
