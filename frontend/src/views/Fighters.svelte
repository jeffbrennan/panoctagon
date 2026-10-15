<script lang="ts">
  import { api, errorMessage, isAbort } from '../lib/api';
  import type { FighterProfile, FighterSummary } from '../lib/types';
  import { date, fighterHref, inches, label, number, odds } from '../lib/format';
  import State from '../lib/State.svelte';
  import Headshot from '../lib/Headshot.svelte';
  import FighterSearch from '../lib/FighterSearch.svelte';
  import Chart from '../lib/Chart.svelte';
  import { timeline, outcomes, strikes, accuracy, targets } from '../lib/fighterCharts';
  let { fighter = '', openFighter }: { fighter?: string; openFighter: (uid: string) => void } =
    $props();
  let profile = $state<FighterProfile | null>(null);
  let error = $state('');
  let loading = $state(true);
  let tab = $state('profile');
  let retry = $state(0);
  let uid = $state('');
  let fights = $derived(profile?.fights || []);
  let reversed = $derived([...fights].reverse());
  let landed = $derived(fights.reduce((sum, f) => sum + (f.strikes_landed || 0), 0));
  let absorbed = $derived(fights.reduce((sum, f) => sum + (f.strikes_absorbed || 0), 0));
  let wins = $derived(fights.filter((f) => f.result === 'WIN'));
  let finishes = $derived(
    wins.filter((f) => ['KO', 'TKO', 'SUB', 'DOC'].includes(f.decision || '')).length,
  );
  $effect(() => {
    const selected = fighter;
    retry;
    const controller = new AbortController();
    loading = true;
    error = '';
    void (async () => {
      try {
        const id =
          selected ||
          (
            await api<FighterSummary[]>('/fighter?name=Max%20Holloway&limit=1', controller.signal)
          )[0]?.fighter_uid;
        if (!id) throw new Error('No fighter records are available.');
        const value = await api<FighterProfile>(
          `/fighter/${encodeURIComponent(id)}/analytics`,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          profile = value;
          uid = id;
        }
      } catch (e) {
        if (!isAbort(e)) error = errorMessage(e);
      } finally {
        if (!controller.signal.aborted) loading = false;
      }
    })();
    return () => controller.abort();
  });
</script>

<div class="page-heading fighter-toolbar">
  <h1>Fighters</h1>
  <FighterSearch onselect={openFighter} />
</div>
{#if error}
  <State title="Unable to load this fighter" message={error} retry={() => retry++} />
{:else if loading}
  <div class="profile-skeleton card-skeleton" aria-hidden="true"></div>
  <State loading message="Loading fighter profile…" />
{:else if profile}
  <section class="fighter-header" aria-labelledby="fighter-name">
    <Headshot {uid} name={profile.bio.full_name} large />
    <div class="fighter-details">
      {#if profile.bio.nickname}<p class="eyebrow">“{profile.bio.nickname}”</p>{/if}
      <h2 id="fighter-name">{profile.bio.full_name}</h2>
      <p class="profile-record">
        {profile.record.wins}-{profile.record.losses}-{profile.record
          .draws}{#if profile.record.no_contests}<span class="muted">
            · {profile.record.no_contests} NC</span
          >{/if}<span class="muted"> · UFC record</span>
      </p>
      <dl class="bio">
        <div>
          <dt>Stance</dt>
          <dd>{profile.bio.stance || '—'}</dd>
        </div>
        <div>
          <dt>Height</dt>
          <dd>{inches(profile.bio.height_inches)}</dd>
        </div>
        <div>
          <dt>Reach</dt>
          <dd>{inches(profile.bio.reach_inches)}</dd>
        </div>
        {#if profile.bio.style}<div>
            <dt>Style</dt>
            <dd>{profile.bio.style}</dd>
          </div>{/if}
      </dl>
    </div>
  </section>
  <div class="subnav" role="tablist" aria-label="Fighter details">
    {#each ['profile', 'history', 'striking'] as item}<button
        id={`tab-${item}`}
        role="tab"
        aria-selected={tab === item}
        aria-controls={`panel-${item}`}
        class:active={tab === item}
        onclick={() => (tab = item)}>{label(item)}</button
      >{/each}
  </div>
  <div role="tabpanel" tabindex="0" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
    {#if !fights.length}<State
        title="No UFC fight history"
        message="Career statistics will appear when completed fights are available."
      />
    {:else if tab === 'profile'}
      <dl class="metrics">
        <div class="metric">
          <dt>Total fights</dt>
          <dd>{profile.record.total_fights}</dd>
        </div>
        <div class="metric">
          <dt>UFC wins</dt>
          <dd>{profile.record.wins}</dd>
        </div>
        <div class="metric">
          <dt>Wins by finish</dt>
          <dd>{wins.length ? `${Math.round((finishes / wins.length) * 100)}%` : '—'}</dd>
        </div>
        <div class="metric">
          <dt>Strikes landed</dt>
          <dd>{number(landed)}</dd>
        </div>
        <div class="metric">
          <dt>Strikes absorbed</dt>
          <dd>{number(absorbed)}</dd>
        </div>
      </dl>
      <div class="chart-grid">
        <section class="panel full">
          <div class="panel-heading">
            <div>
              <h3>Career timeline</h3>
              <p>Cumulative total strikes absorbed</p>
            </div>
            <span class="chart-key"><i></i> Win <i class="hollow"></i> Loss</span>
          </div>
          <Chart
            option={timeline(fights)}
            label={`${profile.bio.full_name}: cumulative strikes absorbed across ${fights.length} UFC fights`}
            height={340}
          />
        </section>
        <section class="panel full">
          <div class="panel-heading"><h3>Fight outcome distribution</h3></div>
          <Chart option={outcomes(fights)} label="Wins and losses by finish method" height={260} />
        </section>
      </div>
    {:else if tab === 'history'}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex (Scrollable tables need keyboard access.) -->
      <div class="table-scroll" tabindex="0" role="region" aria-label="Fight history">
        <table class="data-table">
          <thead
            ><tr
              ><th>Result</th><th>Opponent</th><th>Event</th><th>Date</th><th>Method</th><th
                >Round</th
              ><th>Odds</th></tr
            ></thead
          ><tbody
            >{#each reversed as f (f.fight_uid)}<tr
                ><td
                  ><span
                    class="result"
                    class:win={f.result === 'WIN'}
                    class:loss={f.result === 'LOSS'}
                    >{f.result === 'NO_CONTEST' ? 'NC' : f.result}</span
                  ></td
                ><td
                  ><a href={fighterHref(f.opponent_uid)} data-fighter={f.opponent_uid}
                    >{f.opponent_name}</a
                  ></td
                ><td>{f.event_title}</td><td>{date(f.event_date, true)}</td><td
                  >{label(f.decision)}</td
                ><td>{f.decision_round ?? '—'}</td><td>{odds(f.closing_odds)}</td></tr
              >{/each}</tbody
          >
        </table>
      </div>
    {:else}
      <div class="chart-grid">
        <section class="panel full">
          <div class="panel-heading"><h3>Strikes landed vs. absorbed</h3></div>
          <Chart
            option={strikes(fights)}
            label="Total strikes landed and absorbed by fight"
            height={340}
          />
        </section>
        <section class="panel">
          <div class="panel-heading"><h3>Striking accuracy</h3></div>
          <Chart option={accuracy(fights)} label="Total strike accuracy by fight" height={300} />
        </section>
        <section class="panel">
          <div class="panel-heading"><h3>Strike target distribution</h3></div>
          <Chart
            option={targets(fights)}
            label="Significant strikes to head, body, and legs by fight"
            height={300}
          />
        </section>
      </div>
    {/if}
  </div>
{/if}

<style>
  .fighter-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 28px;
  }
  .fighter-header {
    display: flex;
    align-items: center;
    gap: 28px;
  }
  .fighter-details {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .fighter-details h2 {
    font-size: 2rem;
    letter-spacing: -0.06em;
    line-height: 1.3;
  }
  .profile-record {
    font-size: 0.8125rem;
    margin-top: 6px;
  }
  .bio {
    display: flex;
    gap: 28px;
    margin: 18px 0 0;
    flex-wrap: wrap;
  }
  .bio dt {
    font-size: 0.6875rem;
    color: var(--muted);
  }
  .bio dd {
    margin: 0;
    font-size: 0.8125rem;
  }
  .chart-key {
    font-size: 0.625rem;
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    color: var(--muted);
  }
  .chart-key i {
    width: 9px;
    height: 9px;
    border: 1px solid var(--ink);
    background: var(--ink);
    border-radius: 50%;
    display: inline-block;
  }
  .chart-key i.hollow {
    background: transparent;
    margin-left: 8px;
  }
  .profile-skeleton {
    max-width: 700px;
    height: 140px;
  }
  @media (max-width: 640px) {
    .fighter-toolbar {
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
      margin-bottom: 24px;
    }
    .fighter-header {
      gap: 16px;
      align-items: flex-start;
    }
    .fighter-details {
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .fighter-details h2 {
      font-size: 1.35rem;
    }
    .fighter-details .eyebrow {
      font-size: 0.625rem;
    }
    .bio {
      gap: 14px;
      margin-top: 12px;
    }
    .bio dt {
      font-size: 0.625rem;
    }
    .bio dd {
      font-size: 0.75rem;
    }
    .profile-record {
      font-size: 0.6875rem;
    }
    .fighter-header :global(.headshot.large) {
      width: 92px;
      height: 92px;
    }
    .chart-key {
      display: none;
    }
  }
</style>
