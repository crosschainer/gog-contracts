I = importlib


# State
settings = Hash(default_value=None)
stakes = Hash(default_value=0)
total_staked = Variable()


proposal_id = Variable()
finished_proposals = Hash()
sig = Hash(default_value=False)
proposal_details = Hash()
status = Hash()




@construct
def init(token_contract: str = 'con_blubber_contract'):
    settings[OWNER_STR] = ctx.caller
    settings[TOKEN_CONTRACT_STR] = token_contract

    settings[STAKING_LOCKUP_DAYS_STR] = 21
    total_staked.set(0)

    proposal_id.set(0)
    settings[MINIMUM_PROPOSAL_DURATION_STR] = 7 #Number is in days
    settings[REQUIRED_APPROVAL_PERCENTAGE_STR] = 0.5 #Keep this at 50%, unless there are special circumstances
    settings[MINIMUM_QUORUM_STR] = 0.1 #Set minimum amount of votes needed


@export
def stake(amount: float):
    assert amount >= 0, 'Must be non-negative.'
    current_amount = stakes[ctx.caller] or 0
    if current_amount > amount:
        # unstake
        assert (stakes[ctx.caller, 'time'] + datetime.timedelta(days=1) * (settings[STAKING_LOCKUP_DAYS_STR])) <= now, "Cannot unstake yet!"
        amount_to_unstake = current_amount - amount
        I.import_module(settings[TOKEN_CONTRACT_STR]).transfer(
            to=ctx.caller,
            amount=amount_to_unstake
        )
        total_staked.set(total_staked.get() - amount_to_unstake)
    elif current_amount < amount:
        # stake
        amount_to_stake = amount - current_amount
        I.import_module(settings[TOKEN_CONTRACT_STR]).transfer_from(
            to=ctx.this,
            amount=amount_to_stake,
            main_account=ctx.caller
        )
        stakes[ctx.caller, 'time'] = now
        total_staked.set(total_staked.get() + amount_to_stake)
    stakes[ctx.caller] = amount


@export
def create_basic_proposal(voting_time_in_days: int, description: str): 
    assert voting_time_in_days >= settings[MINIMUM_PROPOSAL_DURATION_STR]
    p_id = proposal_id.get()
    proposal_id.set(p_id + 1)
    proposal_details[p_id, "type"] = "basic"
    modify_proposal(p_id, description, voting_time_in_days)
    return p_id


@export
def vote(p_id: int, result: bool): #Vote here
    sig[p_id, ctx.caller] = result
    voters = proposal_details[p_id, "voters"] or []
    assert ctx.caller not in voters, 'You have already voted.'
    voters.append(ctx.caller)
    proposal_details[p_id, "voters"] = voters


@export
def determine_results(p_id: int) -> bool: #Vote resolution takes place here
    assert (proposal_details[p_id, "time"] + datetime.timedelta(days=1) * (proposal_details[p_id, "duration"])) <= now, "Proposal not over!" #Checks if proposal has concluded
    assert finished_proposals[p_id] is not True, "Proposal already resolved" #Checks that the proposal has not been resolved before (to prevent double spends)
    assert p_id < proposal_id.get()
    finished_proposals[p_id] = True #Adds the proposal to the list of resolved proposals
    approvals = 0
    total_votes = 0
    for x in proposal_details[p_id, "voters"]:
        stake = stakes[x] or 0
        if sig[p_id, x] == True:
            approvals += stake
        total_votes += stake
    quorum = total_staked.get()
    if approvals < (quorum * settings[MINIMUM_QUORUM_STR]): #Checks that the minimum approval percentage has been reached (quorum)
        status[p_id] = False
        return False
    if approvals / total_votes >= settings[REQUIRED_APPROVAL_PERCENTAGE_STR]: #Checks that the approval percentage of the votes has been reached (% of total votes)
        status[p_id] = True
        return True
    else:
        status[p_id] = False
        return False


def modify_proposal(p_id: int, description: str, voting_time_in_days: int):
    proposal_details[p_id, "proposal_creator"] = ctx.caller
    proposal_details[p_id, "description"] = description
    proposal_details[p_id, "time"] = now
    proposal_details[p_id, "duration"] = voting_time_in_days
