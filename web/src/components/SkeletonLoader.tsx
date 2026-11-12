import React from "react";
import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className }) => {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-slate-200/80",
        className
      )}
    />
  );
};

export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 4 }) => {
  return (
    <div className="w-full space-y-3">
      <div className="flex items-center gap-4 py-2 border-b border-slate-200">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16 ml-auto" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 py-3">
          <Skeleton className="h-5 w-24" />
          <Skeleton className="h-5 w-56" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-16 ml-auto" />
        </div>
      ))}
    </div>
  );
};

export const CardSkeleton: React.FC = () => {
  return (
    <div className="p-4 border border-slate-200 rounded-lg bg-white space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  );
};

export const TimelineSkeleton: React.FC<{ count?: number }> = ({ count = 3 }) => {
  return (
    <div className="relative border-l-2 border-slate-200 ml-4 pl-6 space-y-8 py-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="relative">
          {/* Timeline Dot Placeholder */}
          <div className="absolute -left-[31px] top-1 w-3 h-3 rounded-full bg-slate-300 animate-pulse ring-4 ring-white" />
          <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
            <Skeleton className="h-3 w-3/4" />
            <div className="flex items-center gap-2 pt-1">
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-5 w-16 ml-auto" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export const StatSkeleton: React.FC = () => {
  return (
    <div className="p-5 bg-white border border-slate-200 rounded-xl space-y-2 shadow-2xs">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-7 w-20" />
      <Skeleton className="h-3 w-36" />
    </div>
  );
};
