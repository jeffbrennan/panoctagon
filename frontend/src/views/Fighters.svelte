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
  let profile = $state.raw<FighterProfile | null>(null);
  let error = $state('');
  let loading = $state(true);
  let tab = $state('profile');
  let retry = $state(0);
  let uid = $state('');
  const tabs = ['profile', 'history', 'striking'];
  let visitedTabs = $state<Record<string, boolean>>({ profile: true });
  function selectTab(next: string) {
    visitedTabs[next] = true;
    tab = next;
  }
  function tabKeys(event: KeyboardEvent, index: number) {
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    selectTab(tabs[next]);
    document.getElementById(`tab-${tab}`)?.focus();
  }
  let fights = $derived(profile?.fights || []);
  let reversed = $derived([...fights].reverse());
  let timelineOption = $derived(timeline(fights));
  let outcomeOption = $derived(outcomes(fights));
  let strikeOption = $derived(strikes(fights));
  let accuracyOption = $derived(accuracy(fights));
  let targetOption = $derived(targets(fights));
  let landed = $derived(fights.reduce((sum, f) => sum + (f.strikes_landed || 0), 0));
  let absorbed = $derived(fights.reduce((sum, f) => sum + (f.strikes_absorbed || 0), 0));
  let landedCoverage = $derived(fights.filter((f) => f.strikes_landed != null).length);
  let absorbedCoverage = $derived(fights.filter((f) => f.strikes_absorbed != null).length);
  let finishes = $derived(
    fights.filter((f) => ['KO', 'TKO', 'SUB', 'Submission'].includes(f.decision || '')).length,
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
  <div>
    <h1>Fighters</h1>
    {#if loading && profile}<span class="profile-loading" role="status">Loading fighter…</span>{/if}
  </div>
  <FighterSearch onselect={openFighter} />
</div>
{#if error}
  <State title="Unable to load this fighter" message={error} retry={() => retry++} />
{:else if loading && !profile}
  <div class="profile-skeleton card-skeleton" aria-hidden="true"></div>
  <State loading message="Loading fighter profile…" />
{:else if profile}
  <div class="fighter-content" class:updating={loading} aria-busy={loading}>
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
      {#each tabs as item, index}<button
          id={`tab-${item}`}
          role="tab"
          aria-selected={tab === item}
          tabindex={tab === item ? 0 : -1}
          onkeydown={(event) => tabKeys(event, index)}
          aria-controls={`panel-${item}`}
          class:active={tab === item}
          onclick={() => selectTab(item)}>{label(item)}</button
        >{/each}
    </div>
    {#if !fights.length}
      <div role="tabpanel" tabindex="0" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        <State
          title="No UFC fight history"
          message="Career statistics will appear when completed fights are available."
        />
      </div>
    {:else}
      {#if visitedTabs.profile}
        <div
          role="tabpanel"
          tabindex="0"
          id="panel-profile"
          aria-labelledby="tab-profile"
          hidden={tab !== 'profile'}
        >
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
              <dt title="UFC fights ending by KO, TKO, or submission, including wins and losses">
                Finish rate
              </dt>
              <dd>{fights.length ? `${((finishes / fights.length) * 100).toFixed(1)}%` : '—'}</dd>
            </div>
            <div class="metric">
              <dt>Recorded strikes landed</dt>
              <dd>{landedCoverage ? number(landed) : 'Unavailable'}</dd>
              {#if landedCoverage < fights.length}<small>Stats available for {landedCoverage} of {fights.length} fights.</small>{/if}
            </div>
            <div class="metric">
              <dt>Recorded strikes absorbed</dt>
              <dd>{absorbedCoverage ? number(absorbed) : 'Unavailable'}</dd>
              {#if absorbedCoverage < fights.length}<small>Stats available for {absorbedCoverage} of {fights.length} fights.</small>{/if}
            </div>
          </dl>
          <div class="chart-grid">
            <section class="panel full">
              <div class="panel-heading">
                <div>
                  <h3>Career timeline</h3>
                  <p>Cumulative recorded strikes absorbed; missing fights appear as gaps</p>
                </div>
                <span class="chart-key"><i></i> Win <i class="hollow"></i> Loss</span>
              </div>
              <Chart
                option={timelineOption}
                label={`${profile.bio.full_name}: cumulative recorded strikes absorbed across ${fights.length} UFC fights; statistics available for ${absorbedCoverage} of ${fights.length} fights, with gaps for missing data`}
                height={340}
              />
            </section>
            <section class="panel full">
              <div class="panel-heading"><h3>Fight outcome distribution</h3></div>
              <Chart option={outcomeOption} label="Wins and losses by finish method" height={260} />
            </section>
          </div>
        </div>
      {/if}
      {#if tab === 'history'}
        <div role="tabpanel" tabindex="0" id="panel-history" aria-labelledby="tab-history">
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
        </div>
      {/if}
      {#if visitedTabs.striking}
        <div
          role="tabpanel"
          tabindex="0"
          id="panel-striking"
          aria-labelledby="tab-striking"
          hidden={tab !== 'striking'}
        >
          <div class="chart-grid">
            <section class="panel full">
              <div class="panel-heading"><h3>Strikes landed vs. absorbed</h3></div>
              <Chart
                option={strikeOption}
                label="Total strikes landed and absorbed by fight"
                height={340}
              />
            </section>
            <section class="panel">
              <div class="panel-heading"><h3>Striking accuracy</h3></div>
              <Chart option={accuracyOption} label="Total strike accuracy by fight" height={300} />
            </section>
            <section class="panel">
              <div class="panel-heading"><h3>Strike target distribution</h3></div>
              <Chart
                option={targetOption}
                label="Significant strikes to head, body, and legs by fight"
                height={300}
              />
            </section>
          </div>
        </div>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .fighter-toolbar > div {
    position: relative;
  }
  .profile-loading {
    position: absolute;
    top: 100%;
    left: 0;
    white-space: nowrap;
    color: var(--muted);
    font-size: 0.75rem;
  }
  .fighter-content {
    transition: opacity 120ms ease;
  }
  .fighter-content.updating {
    opacity: 0.55;
    pointer-events: none;
  }
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
    font-size: 0.75rem;
    color: var(--muted);
  }
  .bio dd {
    margin: 0;
    font-size: 0.8125rem;
  }
  .chart-key {
    font-size: 0.75rem;
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
      font-size: 0.75rem;
    }
    .bio {
      gap: 14px;
      margin-top: 12px;
    }
    .bio dt {
      font-size: 0.75rem;
    }
    .bio dd {
      font-size: 0.75rem;
    }
    .profile-record {
      font-size: 0.75rem;
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
