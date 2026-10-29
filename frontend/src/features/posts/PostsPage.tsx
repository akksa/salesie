import { Images, Plus } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { useProducts } from "@/features/catalog/api";
import { usePosts } from "./api";
import { PostForm } from "./PostForm";
import { PostRow } from "./PostRow";

export function PostsPage() {
  const posts = usePosts();
  const products = useProducts();
  const [registering, setRegistering] = useState(false);
  const list = posts.data ?? [];
  const productList = products.data ?? [];
  const unlinked = list.filter((p) => p.product_id === null).length;

  const registerButton = (
    <Button onClick={() => setRegistering(true)} icon={<Plus className="size-4" aria-hidden />}>
      Register post
    </Button>
  );

  return (
    <>
      <PageHeader
        eyebrow="Posts"
        title="Posts that sell"
        description={
          unlinked > 0
            ? `${unlinked} post${unlinked === 1 ? " isn't" : "s aren't"} linked to a product yet. Link them so comments turn into leads for the right item.`
            : "Each post points at a product, so a comment becomes a lead for that item."
        }
        actions={list.length > 0 ? registerButton : null}
      />

      {posts.isError ? (
        <ErrorBanner error={posts.error} onRetry={() => posts.refetch()} className="mb-4" />
      ) : null}
      {products.isError ? (
        <ErrorBanner error={products.error} onRetry={() => products.refetch()} className="mb-4" />
      ) : null}

      <Card className="overflow-hidden">
        {posts.isPending ? <SkeletonRows rows={3} /> : null}
        {posts.isSuccess && list.length === 0 ? (
          <EmptyState
            icon={<Images className="size-6" aria-hidden />}
            title="No posts registered"
            action={registerButton}
          >
            Register an Instagram post and pick the product it shows. Later, Salesie will pick up new posts on
            its own.
          </EmptyState>
        ) : null}
        {list.length > 0 ? (
          <ul className="divide-y divide-border">
            {list.map((post, index) => (
              <PostRow key={post.id} post={post} products={productList} index={index} />
            ))}
          </ul>
        ) : null}
      </Card>

      <Modal
        open={registering}
        onClose={() => setRegistering(false)}
        title="Register a post"
        description="Tell Salesie which product an Instagram post is selling."
      >
        {registering ? <PostForm products={productList} onDone={() => setRegistering(false)} /> : null}
      </Modal>
    </>
  );
}
