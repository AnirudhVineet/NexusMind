"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteDocument,
  getDocumentStatus,
  listDocuments,
  uploadDocument,
} from "@/services/documents";

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    refetchInterval: 5000,
  });
}

export function useDocumentStatus(id: string | null, enabled = true) {
  return useQuery({
    queryKey: ["document-status", id],
    queryFn: () => getDocumentStatus(id!),
    enabled: !!id && enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 3000;
      if (data.processing_status === "complete" || data.processing_status === "failed") {
        return false;
      }
      return 3000;
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}
