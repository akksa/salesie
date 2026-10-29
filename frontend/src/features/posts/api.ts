import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import type { PostIn, PostOut, PostUpdate } from "@/api/types";

export function usePosts() {
  return useQuery({
    queryKey: queryKeys.posts,
    queryFn: () => api.get<PostOut[]>("/api/posts"),
  });
}

export function useCreatePost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PostIn) => api.post<PostOut>("/api/posts", body),
    onSuccess: (post) => {
      queryClient.setQueryData<PostOut[]>(queryKeys.posts, (old) => (old ? [post, ...old] : [post]));
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts });
    },
  });
}

export function useUpdatePost() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: PostUpdate }) =>
      api.patch<PostOut>(`/api/posts/${id}`, body),
    onSuccess: (post) => {
      queryClient.setQueryData<PostOut[]>(queryKeys.posts, (old) =>
        old?.map((p) => (p.id === post.id ? post : p)),
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts });
    },
  });
}
