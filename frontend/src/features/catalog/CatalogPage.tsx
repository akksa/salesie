import { Package, Plus } from "lucide-react";
import { useState } from "react";
import type { ProductOut } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCurrency } from "@/features/settings/api";
import { useProducts } from "./api";
import { ProductCard } from "./ProductCard";
import { ProductForm } from "./ProductForm";

/** `null` = closed, `"new"` = create, a product = edit. */
type Editing = null | "new" | ProductOut;

function CatalogSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="Loading products">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="overflow-hidden">
          <Skeleton className="aspect-[4/3] h-auto rounded-none" />
          <div className="space-y-2 p-4">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </Card>
      ))}
    </div>
  );
}

export function CatalogPage() {
  const products = useProducts();
  const currency = useCurrency();
  const [editing, setEditing] = useState<Editing>(null);
  const close = () => setEditing(null);
  const list = products.data ?? [];
  const activeCount = list.filter((p) => p.status === "active").length;

  const addButton = (
    <Button onClick={() => setEditing("new")} icon={<Plus className="size-4" aria-hidden />}>
      Add product
    </Button>
  );

  return (
    <>
      <PageHeader
        eyebrow="Catalog"
        title="What you sell"
        description={
          products.data
            ? `${list.length} product${list.length === 1 ? "" : "s"}, ${activeCount} active. Posts link to these so every lead knows what they wanted.`
            : "Posts link to these so every lead knows what they wanted."
        }
        actions={list.length > 0 ? addButton : null}
      />

      {products.isError ? (
        <ErrorBanner error={products.error} onRetry={() => products.refetch()} className="mb-4" />
      ) : null}
      {products.isPending ? <CatalogSkeleton /> : null}

      {products.isSuccess && list.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Package className="size-6" aria-hidden />}
            title="Your catalog is empty"
            action={addButton}
          >
            Add the products you sell on Instagram and WhatsApp. Salesie links posts and leads back to them.
          </EmptyState>
        </Card>
      ) : null}

      {list.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((product, index) => (
            <ProductCard
              key={product.id}
              index={index}
              product={product}
              currency={currency}
              onEdit={() => setEditing(product)}
            />
          ))}
        </div>
      ) : null}

      <Modal
        open={editing !== null}
        onClose={close}
        title={editing === "new" ? "Add a product" : "Edit product"}
        description={editing === "new" ? "Prices are in your business currency." : undefined}
      >
        {editing !== null ? (
          <ProductForm
            key={editing === "new" ? "new" : editing.id}
            product={editing === "new" ? null : editing}
            currency={currency}
            onDone={close}
          />
        ) : null}
      </Modal>
    </>
  );
}
