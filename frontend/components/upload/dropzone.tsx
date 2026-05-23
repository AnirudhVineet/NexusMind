"use client";

import { useDropzone } from "react-dropzone";

import { cn } from "@/lib/utils";

const MAX_BYTES = 50 * 1024 * 1024;

const ACCEPT = {
  "application/pdf": [".pdf"],
  "text/plain": [".txt"],
  "text/markdown": [".md"],
};

interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function DropZone({ onFiles, disabled }: Props) {
  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop: (accepted) => onFiles(accepted),
    accept: ACCEPT,
    maxSize: MAX_BYTES,
    disabled,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors",
        isDragActive
          ? "border-accent bg-accent/10"
          : "border-border bg-surface hover:bg-border/40",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <input {...getInputProps()} />
      <p className="text-base font-medium">
        {isDragActive ? "Drop to upload" : "Drag & drop, or click to choose files"}
      </p>
      <p className="text-xs text-muted mt-2">PDF, TXT, or MD · up to 50 MB</p>
      {fileRejections.length > 0 && (
        <ul className="mt-3 text-sm text-red-400">
          {fileRejections.map(({ file, errors }) => (
            <li key={file.name}>
              {file.name}: {errors[0]?.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
