"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createAnnotation,
  deleteAnnotation,
  listAnnotations,
  updateAnnotation,
  type AnnotationFilters,
  type CreateAnnotationBody,
  type UpdateAnnotationBody,
} from "@/services/annotations";
import { getDocumentChunks } from "@/services/documents";

export function useAnnotations(filters: AnnotationFilters = {}) {
  return useQuery({
    queryKey: ["annotations", filters],
    queryFn: () => listAnnotations(filters),
  });
}

export function useDocumentChunks(documentId: string | null) {
  return useQuery({
    queryKey: ["document-chunks", documentId],
    queryFn: () => getDocumentChunks(documentId!),
    enabled: !!documentId,
  });
}

export function useCreateAnnotation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateAnnotationBody) => createAnnotation(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations"] }),
  });
}

export function useUpdateAnnotation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateAnnotationBody }) =>
      updateAnnotation(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations"] }),
  });
}

export function useDeleteAnnotation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAnnotation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["annotations"] }),
  });
}
