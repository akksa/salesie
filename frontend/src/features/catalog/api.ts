import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { ProductIn, ProductOut, ProductUpdate } from "@/api/types";

export function useProducts() {
  return useQuery({
    queryKey: queryKeys.products,
    queryFn: () => api.get<ProductOut[]>("/api/products"),
  });
}

function useInvalidateCatalog() {
  const queryClient = useQueryClient();
  return () => {
    // Product names are denormalised into posts, deals and contacts.
    void queryClient.invalidateQueries({ queryKey: queryKeys.products });
    void queryClient.invalidateQueries({ queryKey: queryKeys.posts });
    void queryClient.invalidateQueries({ queryKey: queryKeys.deals });
    void queryClient.invalidateQueries({ queryKey: queryKeys.contacts });
  };
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateCatalog();
  return useMutation({
    mutationFn: (body: ProductIn) => api.post<ProductOut>("/api/products", body),
    onSuccess: (product) => {
      queryClient.setQueryData<ProductOut[]>(queryKeys.products, (old) =>
        old ? [product, ...old] : [product],
      );
      invalidate();
    },
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateCatalog();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ProductUpdate }) =>
      api.patch<ProductOut>(`/api/products/${id}`, body),
    onSuccess: (product) => {
      queryClient.setQueryData<ProductOut[]>(queryKeys.products, (old) =>
        old?.map((p) => (p.id === product.id ? product : p)),
      );
      invalidate();
    },
  });
}
