<script lang="ts">
  let {
    loading = false,
    message = '',
    retry,
    title = '',
  }: { loading?: boolean; message?: string; title?: string; retry?: () => void } = $props();
</script>

<div class="state" class:loading role={loading ? 'status' : undefined} aria-live="polite">
  {#if loading}<span class="spinner" aria-hidden="true"></span>{/if}
  {#if title}<h2>{title}</h2>{/if}
  <p>{message || (loading ? 'Loading data…' : 'No results found.')}</p>
  {#if retry}<button class="button" onclick={retry}>Try again</button>{/if}
</div>
