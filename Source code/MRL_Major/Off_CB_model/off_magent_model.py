import copy
import torch
import torch.nn as nn
import torch.nn.functional as F

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# device = torch.device('cpu')


class CB_Encoder(nn.Module):
    """Encodes the static & dynamic states using 1d convolution neural network."""

    def __init__(self, input_size, hidden_size):
        super(CB_Encoder, self).__init__()
        self.conv = nn.Conv1d(input_size, hidden_size, kernel_size=1)

    def forward(self, input):
        output = self.conv(input)
        return output  # (batch, hidden_size, seq_len)


class CB_Attention(nn.Module):
    """Calculates attention over the input nodes given the current state."""

    def __init__(self, hidden_size):
        super(CB_Attention, self).__init__()

        # W processes features from static decoder elements
        self.v = nn.Parameter(torch.zeros((1, 1, hidden_size), device=device, requires_grad=True))

        self.W = nn.Parameter(torch.zeros((1, hidden_size, 3 * hidden_size), device=device, requires_grad=True))

    def forward(self, static_hidden, dynamic_hidden, decoder_hidden):

        batch_size, hidden_size, _ = static_hidden.size()

        hidden = decoder_hidden.unsqueeze(2).expand_as(static_hidden)
        hidden = torch.cat((static_hidden, dynamic_hidden, hidden), 1)

        # Broadcast some dimensions so we can do batch-matrix-multiply
        v = self.v.expand(batch_size, 1, hidden_size)
        W = self.W.expand(batch_size, hidden_size, -1)

        attns = torch.bmm(v, torch.tanh(torch.bmm(W, hidden)))
        attns = F.softmax(attns, dim=2)  # (batch, seq_len)
        return attns


class CB_Agent(nn.Module):
    """Calculates the next state given the previous state and input embeddings."""

    def __init__(self, hidden_size, num_layers=1, dropout=0.2):
        super(CB_Agent, self).__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # Used to calculate probability of selecting next state
        self.v = nn.Parameter(torch.zeros((1, 1, hidden_size), device=device, requires_grad=True))

        self.W = nn.Parameter(torch.zeros((1, hidden_size, 2 * hidden_size), device=device, requires_grad=True))

        # Used to compute a representation of the current decoder output
        self.gru = nn.GRU(hidden_size, hidden_size, num_layers, batch_first=True,
                          dropout=dropout if num_layers > 1 else 0)
        self.encoder_attn = CB_Attention(hidden_size)

        self.drop_rnn = nn.Dropout(p=dropout)
        self.drop_hh = nn.Dropout(p=dropout)

    def forward(self, static_hidden, dynamic_hidden, decoder_hidden, last_hh):

        rnn_out, last_hh = self.gru(decoder_hidden.transpose(2, 1), last_hh)
        rnn_out = rnn_out.squeeze(1)

        # Always apply dropout on the gated recurrent units output
        rnn_out = self.drop_rnn(rnn_out)
        if self.num_layers == 1:
            # If > 1 layer dropout is already applied
            last_hh = self.drop_hh(last_hh) 

        # Given a summary of the output, find an  input context
        enc_attn = self.encoder_attn(static_hidden, dynamic_hidden, rnn_out)
        context = enc_attn.bmm(static_hidden.permute(0, 2, 1))  # (B, 1, num_feats)

        # Calculate the next output using batch-matrix-multiply
        context = context.transpose(1, 2).expand_as(static_hidden)
        energy = torch.cat((static_hidden, context), dim=1)  # (B, num_feats, seq_len)

        v = self.v.expand(static_hidden.size(0), -1, -1)
        W = self.W.expand(static_hidden.size(0), -1, -1)

        probs = torch.bmm(v, torch.tanh(torch.bmm(W, energy))).squeeze(1)

        return probs, last_hh


class MA_CB_RP_Major(nn.Module):
    ''' ---------------------------------------
    (1)static_size：int, defines how many features are in the static elements of the model.
    (2)dynamic_size：int > 1, defines how many features are in the dynamic elements of the model.
    (3)hidden_size：int, defines all static, dynamic, and decoder output units.
    (4)Agent_n: int, number of agents.
    (5)update_fn：this method is used to calculate the input dynamic element to be updated.
    (6)mask_fn：this method is used to help speed up network training by providing a sort of "rule" guideline for the algorithm.
    (7)mask_start: this method is used to process the action space of each agent through a masking mechanism.
    (8)update_tw: this method is used to process each travel demand for each station through the matching mechanism.
    (9)update_od: This method is used to update the travel demand distribution across the road network and generate new travel demand in the road network.
    (10)num_layers：int, specifies the number of hidden layers to use in the decoder
    (11)dropout：float, define the exit rate of the decoder to prevent overfitting'''
    def __init__(self, static_size, dynamic_size, hidden_size, Agent_n,
                 update_fn=None, mask_fn=None, mask_start=None, update_tw=None, update_od=None, num_layers=1, dropout=0.):
        super(MA_CB_RP_Major, self).__init__()

        if dynamic_size < 1:
            raise ValueError(':param dynamic_size: must be > 0, even if the '
                             'problem has no dynamic elements')
        self.agent_number = Agent_n
        self.update_fn = update_fn
        self.mask_fn = mask_fn
        self.mask_start = mask_start
        self.update_tw = update_tw
        self.update_od = update_od

        # Define the static_encoder model. Environment state shared by all agents.
        self.static_encoder = CB_Encoder(static_size, hidden_size)
        # Define the agent_dynamic_encoder models. Each agent has a dynamic encoder model.
        self.agent_dynamic_encoder1 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder2 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder3 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder4 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder5 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder6 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder7 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder8 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder9 = CB_Encoder(dynamic_size, hidden_size)
        self.agent_dynamic_encoder10 = CB_Encoder(dynamic_size, hidden_size)


        # Define the agent_dynamic_encoder models. Each agent has a decoder model.
        # self.agent_decoder = [CB_Encoder(dynamic_size, hidden_size) for i in range(self.agent_number)]
        self.agent_decoder1 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder2 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder3 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder4 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder5 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder6 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder7 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder8 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder9 = CB_Encoder(static_size, hidden_size)
        self.agent_decoder10 = CB_Encoder(static_size, hidden_size)

        # Define the agent_CB_Agent models. Each agent has a CB_Agent model.
        # self.agent_CB_Agent = [CB_Agent(hidden_size, num_layers, dropout) for i in range(self.agent_number)]
        self.agent_pointer1 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer2 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer3 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer4 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer5 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer6 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer7 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer8 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer9 = CB_Agent(hidden_size, num_layers, dropout)
        self.agent_pointer10 = CB_Agent(hidden_size, num_layers, dropout)

        for p in self.parameters():
            if len(p.shape) > 1:
                nn.init.xavier_uniform_(p)
        # Used as a proxy initial state in the decoder when not specified
        self.x0 = torch.zeros((1, static_size, 1), requires_grad=True, device=device)


    def forward(self, static, dynamic1, dynamic2, dynamic3, dynamic4, dynamic5, dynamic6, dynamic7, dynamic8,
                dynamic9, dynamic10, record1, record2, record3, travel_time_G, up_station,
                all_station, decoder_input=None, last_hh=None):
        '''
            (1)static：static information in the CB operating environment, (batch_size, features, num_stations).
            (2)dynamic：dynamic information observed by each agent in the CB operating environment, [(batch_size, features, num_stations), (batch_size, features, num_stations),...].
            (3)record：important information recorded in the CB operating environment, used to calculate the return function, [(batch_size, features, num_stations), (batch_size, features, num_stations),...].
            (4)travel_time_G: travel time matrix for road environment.
            (5)up_station：list of boarding stations in the origin area.
            (6)all_station：list of all stations in the road network.
            (7)decoder_input: The input of the agent decoder, (batch_size, features).
            (8)last_hh: Last hidden state of gated recurrent units, (batch_size, num_hidden).'''
        last_hh1 = last_hh
        last_hh2 = last_hh
        last_hh3 = last_hh
        last_hh4 = last_hh
        last_hh5 = last_hh
        last_hh6 = last_hh
        last_hh7 = last_hh
        last_hh8 = last_hh
        last_hh9 = last_hh
        last_hh10 = last_hh
        dynamic0 = [dynamic1.clone(), dynamic2.clone(), dynamic3.clone(), dynamic4.clone(), dynamic5.clone(),
                    dynamic6.clone(), dynamic7.clone(), dynamic8.clone(), dynamic9.clone(), dynamic10.clone()]
        decision_list = [[] for i in range(len(static[:]))]  # Agents decision list
        # decision_point = torch.ones(len(static[:]), 3, len(all_station)) * np.inf
        for ns in range(len(decision_list)):
            for a_idx in range(1, self.agent_number):
                decision_list[ns].append([dynamic0[a_idx-1][ns][7][0].item(), a_idx])
        for so in range(len(decision_list)):  # Decision ranking
            list.sort(decision_list[so], key=(lambda x: [x[0]]))
        batch_size, input_size, sequence_size = static.size()

        decoder_input1 = decoder_input
        decoder_input2 = decoder_input
        decoder_input3 = decoder_input
        decoder_input4 = decoder_input
        decoder_input5 = decoder_input
        decoder_input6 = decoder_input
        decoder_input7 = decoder_input
        decoder_input8 = decoder_input
        decoder_input9 = decoder_input
        decoder_input10 = decoder_input
        if decoder_input is None:
            decoder_input1 = self.x0.expand(batch_size, -1, -1)
            decoder_input2 = self.x0.expand(batch_size, -1, -1)
            decoder_input3 = self.x0.expand(batch_size, -1, -1)
            decoder_input4 = self.x0.expand(batch_size, -1, -1)
            decoder_input5 = self.x0.expand(batch_size, -1, -1)
            decoder_input6 = self.x0.expand(batch_size, -1, -1)
            decoder_input7 = self.x0.expand(batch_size, -1, -1)
            decoder_input8 = self.x0.expand(batch_size, -1, -1)
            decoder_input9 = self.x0.expand(batch_size, -1, -1)
            decoder_input10 = self.x0.expand(batch_size, -1, -1)
        #  Agents' mask list
        mask1 = torch.ones(batch_size, sequence_size, device=device)
        mask2 = torch.ones(batch_size, sequence_size, device=device)
        mask3 = torch.ones(batch_size, sequence_size, device=device)
        mask4 = torch.ones(batch_size, sequence_size, device=device)
        mask5 = torch.ones(batch_size, sequence_size, device=device)
        mask6 = torch.ones(batch_size, sequence_size, device=device)
        mask7 = torch.ones(batch_size, sequence_size, device=device)
        mask8 = torch.ones(batch_size, sequence_size, device=device)
        mask9 = torch.ones(batch_size, sequence_size, device=device)
        mask10 = torch.ones(batch_size, sequence_size, device=device)
        # Agents' judgment list
        mask_judge = torch.ones(batch_size, sequence_size, device=device)
        # This means that all vehicles depart from CP
        mask1[:, 0] = 0
        mask1[:, len(up_station):] = 0
        mask2[:, 0] = 0
        mask2[:, len(up_station):] = 0
        mask3[:, 0] = 0
        mask3[:, len(up_station):] = 0
        mask4[:, 0] = 0
        mask4[:, len(up_station):] = 0
        mask5[:, 0] = 0
        mask5[:, len(up_station):] = 0
        mask6[:, 0] = 0
        mask6[:, len(up_station):] = 0
        mask7[:, 0] = 0
        mask7[:, len(up_station):] = 0
        mask8[:, 0] = 0
        mask8[:, len(up_station):] = 0
        mask9[:, 0] = 0
        mask9[:, len(up_station):] = 0
        mask10[:, 0] = 0
        mask10[:, len(up_station):] = 0

        agent_mask1 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask2 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask3 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask4 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask5 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask6 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask7 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask8 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask9 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask10 = torch.ones(batch_size, sequence_size, device=device)
        agent_mask1[:, 0] = 0
        agent_mask2[:, 0] = 0
        agent_mask3[:, 0] = 0
        agent_mask4[:, 0] = 0
        agent_mask5[:, 0] = 0
        agent_mask6[:, 0] = 0
        agent_mask7[:, 0] = 0
        agent_mask8[:, 0] = 0
        agent_mask9[:, 0] = 0
        agent_mask10[:, 0] = 0
        decision_mask_dict = {}  # Decision mask dictionary
        tw_mask = torch.ones(batch_size, 3, len(all_station), device=device)  # Mask of all travel demands for all stations
        tw_mask[:, 0:, 0] = 0  # This means that CP has no travel demand
        tw_mask[:, 0:, len(up_station):] = 0  # All alighting stations have no travel demand
        # This dictionary is used to store all the routes constructed by the agent, i.e. the sequence of stations.
        tour_idx = {}
        tour_logp = {}
        tour_idx_dict = {}
        static_hidden = self.static_encoder(static)

        dynamic_hidden1 = self.agent_dynamic_encoder1(dynamic1)
        dynamic_hidden2 = self.agent_dynamic_encoder2(dynamic2)
        dynamic_hidden3 = self.agent_dynamic_encoder3(dynamic3)
        dynamic_hidden4 = self.agent_dynamic_encoder4(dynamic4)
        dynamic_hidden5 = self.agent_dynamic_encoder5(dynamic5)
        dynamic_hidden6 = self.agent_dynamic_encoder6(dynamic6)
        dynamic_hidden7 = self.agent_dynamic_encoder7(dynamic7)
        dynamic_hidden8 = self.agent_dynamic_encoder8(dynamic8)
        dynamic_hidden9 = self.agent_dynamic_encoder9(dynamic9)
        dynamic_hidden10 = self.agent_dynamic_encoder10(dynamic10)
        for a_id in range(1, self.agent_number):
            if a_id not in tour_idx.keys():
                tour_idx[a_id] = []
                tour_idx_dict[a_id] = [[] for i in range(len(static[:]))]
            if a_id not in tour_logp.keys():
                tour_logp[a_id] = []
            if a_id not in decision_mask_dict.keys():
                decision_mask_dict[a_id] = [0 for i in range(batch_size)]
        max_steps = sequence_size if self.mask_fn is None else 1000  # Decision step
        dynamic = [dynamic1.clone(), dynamic2.clone(), dynamic3.clone(), dynamic4.clone(), dynamic5.clone(),
                   dynamic6.clone(), dynamic7.clone(), dynamic8.clone(), dynamic9.clone(), dynamic10.clone()]
        for _ in range(max_steps):
            '''Update decision time'''
            for a_id in range(1, self.agent_number):
                decision_mask_dict[a_id] = [0 for i in range(batch_size)]
            cy_decision_list = copy.deepcopy(decision_list)
            dynamic1_cl0 = dynamic1.clone()
            dynamic2_cl0 = dynamic2.clone()
            dynamic3_cl0 = dynamic3.clone()
            dynamic4_cl0 = dynamic4.clone()
            dynamic5_cl0 = dynamic5.clone()
            dynamic6_cl0 = dynamic6.clone()
            dynamic7_cl0 = dynamic7.clone()
            dynamic8_cl0 = dynamic8.clone()
            dynamic9_cl0 = dynamic9.clone()
            dynamic10_cl0 = dynamic10.clone()
            for ns0, ns0a in enumerate(cy_decision_list):
                if ns0a:
                    decision_mask_dict[ns0a[0][1]][ns0] = 1
                    decision_list[ns0].remove(ns0a[0])
                    dynamic1_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic2_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic3_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic4_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic5_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic6_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic7_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic8_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic9_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                    dynamic10_cl0[ns0][5] = dynamic[ns0a[0][1] - 1][ns0][10].clone()
                for n0 in range(1, len(ns0a)):
                    if ns0a[n0][0] == ns0a[0][0]:
                        decision_mask_dict[ns0a[n0][1]][ns0] = 1
                        decision_list[ns0].remove(ns0a[n0])
            dynamic1 = torch.as_tensor(dynamic1_cl0.clone().data, device=dynamic1.device)
            dynamic2 = torch.as_tensor(dynamic2_cl0.clone().data, device=dynamic2.device)
            dynamic3 = torch.as_tensor(dynamic3_cl0.clone().data, device=dynamic3.device)
            dynamic4 = torch.as_tensor(dynamic4_cl0.clone().data, device=dynamic4.device)
            dynamic5 = torch.as_tensor(dynamic5_cl0.clone().data, device=dynamic5.device)
            dynamic6 = torch.as_tensor(dynamic6_cl0.clone().data, device=dynamic6.device)
            dynamic7 = torch.as_tensor(dynamic7_cl0.clone().data, device=dynamic7.device)
            dynamic8 = torch.as_tensor(dynamic8_cl0.clone().data, device=dynamic8.device)
            dynamic9 = torch.as_tensor(dynamic9_cl0.clone().data, device=dynamic9.device)
            dynamic10 = torch.as_tensor(dynamic10_cl0.clone().data, device=dynamic10.device)
            dynamic_uod = [dynamic1.clone(), dynamic2.clone(), dynamic3.clone(), dynamic4.clone(), dynamic5.clone(),
                           dynamic6.clone(), dynamic7.clone(), dynamic8.clone(), dynamic9.clone(), dynamic10.clone()]
            constraint_uod = [record1.clone(), record2.clone(), record3.clone()]
            dynamic, constraint = self.update_od(dynamic_uod, constraint_uod, static, up_station, tw_mask)
            dynamic1_cl1 = dynamic[0].clone()
            dynamic2_cl1 = dynamic[1].clone()
            dynamic3_cl1 = dynamic[2].clone()
            dynamic4_cl1 = dynamic[3].clone()
            dynamic5_cl1 = dynamic[4].clone()
            dynamic6_cl1 = dynamic[5].clone()
            dynamic7_cl1 = dynamic[6].clone()
            dynamic8_cl1 = dynamic[7].clone()
            dynamic9_cl1 = dynamic[8].clone()
            dynamic10_cl1 = dynamic[9].clone()
            dynamic1 = torch.as_tensor(dynamic1_cl1.clone().data, device=dynamic1.device)
            dynamic2 = torch.as_tensor(dynamic2_cl1.clone().data, device=dynamic2.device)
            dynamic3 = torch.as_tensor(dynamic3_cl1.clone().data, device=dynamic3.device)
            dynamic4 = torch.as_tensor(dynamic4_cl1.clone().data, device=dynamic4.device)
            dynamic5 = torch.as_tensor(dynamic5_cl1.clone().data, device=dynamic5.device)
            dynamic6 = torch.as_tensor(dynamic6_cl1.clone().data, device=dynamic6.device)
            dynamic7 = torch.as_tensor(dynamic7_cl1.clone().data, device=dynamic7.device)
            dynamic8 = torch.as_tensor(dynamic8_cl1.clone().data, device=dynamic8.device)
            dynamic9 = torch.as_tensor(dynamic9_cl1.clone().data, device=dynamic9.device)
            dynamic10 = torch.as_tensor(dynamic10_cl1.clone().data, device=dynamic10.device)
            record1_cl = constraint[0].clone()
            record2_cl = constraint[1].clone()
            record3_cl = constraint[2].clone()
            record1 = torch.as_tensor(record1_cl.clone().data, device=record1.device)
            record2 = torch.as_tensor(record2_cl.clone().data, device=record2.device)
            record3 = torch.as_tensor(record3_cl.clone().data, device=record3.device)
            decision_agent_id = []
            for a_nn in range(1, self.agent_number):
                decision_agent_id.append(a_nn)
            mask_judge_x = agent_mask1.clone() + agent_mask2.clone() + agent_mask3.clone() + agent_mask4.clone() +\
                           agent_mask5.clone() + agent_mask6.clone() + agent_mask7.clone() + agent_mask8.clone() + \
                           agent_mask9.clone() + agent_mask10.clone()
            mask_judge = torch.as_tensor(mask_judge_x.clone().data, device=mask_judge.device)
            if not mask_judge.byte().any():
                break
            for ag_id in range(1, self.agent_number):
                if ag_id == 1:
                    mask1_start, agent_mask1_start = self.mask_start(mask1, dynamic1, up_station, tw_mask, agent_mask1)
                    mask1 = torch.as_tensor(mask1_start.clone().data, device=mask1.device)
                    agent_mask1 = torch.as_tensor(agent_mask1_start.clone().data, device=agent_mask1.device)
                    if not mask1.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask1 = (mask1.clone()).sum(1).eq(0)
                    if visit_mask1.any():
                        visit_idx_mask1 = visit_mask1.nonzero().squeeze()
                        mask1[visit_idx_mask1, 0] = 1
                        mask1[visit_idx_mask1, 1:] = 0
                if ag_id == 2:
                    mask2_start, agent_mask2_start = self.mask_start(mask2, dynamic2, up_station, tw_mask, agent_mask2)
                    mask2 = torch.as_tensor(mask2_start.clone().data, device=mask2.device)
                    agent_mask2 = torch.as_tensor(agent_mask2_start.clone().data, device=agent_mask2.device)
                    if not mask2.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask2 = (mask2.clone()).sum(1).eq(0)
                    if visit_mask2.any():
                        visit_idx_mask2 = visit_mask2.nonzero().squeeze()
                        mask2[visit_idx_mask2, 0] = 1
                        mask2[visit_idx_mask2, 1:] = 0
                if ag_id == 3:
                    mask3_start, agent_mask3_start = self.mask_start(mask3, dynamic3, up_station, tw_mask, agent_mask3)
                    mask3 = torch.as_tensor(mask3_start.clone().data, device=mask3.device)
                    agent_mask3 = torch.as_tensor(agent_mask3_start.clone().data, device=agent_mask3.device)
                    if not mask3.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask3 = (mask3.clone()).sum(1).eq(0)
                    if visit_mask3.any():
                        visit_idx_mask3 = visit_mask3.nonzero().squeeze()
                        mask3[visit_idx_mask3, 0] = 1
                        mask3[visit_idx_mask3, 1:] = 0
                if ag_id == 4:
                    mask4_start, agent_mask4_start = self.mask_start(mask4, dynamic4, up_station, tw_mask, agent_mask4)
                    mask4 = torch.as_tensor(mask4_start.clone().data, device=mask4.device)
                    agent_mask4 = torch.as_tensor(agent_mask4_start.clone().data, device=agent_mask4.device)
                    if not mask4.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask4 = (mask4.clone()).sum(1).eq(0)
                    if visit_mask4.any():
                        visit_idx_mask4 = visit_mask4.nonzero().squeeze()
                        mask4[visit_idx_mask4, 0] = 1
                        mask4[visit_idx_mask4, 1:] = 0
                if ag_id == 5:
                    mask5_start, agent_mask5_start = self.mask_start(mask5, dynamic5, up_station, tw_mask, agent_mask5)
                    mask5 = torch.as_tensor(mask5_start.clone().data, device=mask5.device)
                    agent_mask5 = torch.as_tensor(agent_mask5_start.clone().data, device=agent_mask5.device)
                    if not mask5.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask5 = (mask5.clone()).sum(1).eq(0)
                    if visit_mask5.any():
                        visit_idx_mask5 = visit_mask5.nonzero().squeeze()
                        mask5[visit_idx_mask5, 0] = 1
                        mask5[visit_idx_mask5, 1:] = 0
                if ag_id == 6:
                    mask6_start, agent_mask6_start = self.mask_start(mask6, dynamic6, up_station, tw_mask, agent_mask6)
                    mask6 = torch.as_tensor(mask6_start.clone().data, device=mask6.device)
                    agent_mask6 = torch.as_tensor(agent_mask6_start.clone().data, device=agent_mask6.device)
                    if not mask6.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask6 = (mask6.clone()).sum(1).eq(0)
                    if visit_mask6.any():
                        visit_idx_mask6 = visit_mask6.nonzero().squeeze()
                        mask6[visit_idx_mask6, 0] = 1
                        mask6[visit_idx_mask6, 1:] = 0
                if ag_id == 7:
                    mask7_start, agent_mask7_start = self.mask_start(mask7, dynamic7, up_station, tw_mask, agent_mask7)
                    mask7 = torch.as_tensor(mask7_start.clone().data, device=mask7.device)
                    agent_mask7 = torch.as_tensor(agent_mask7_start.clone().data, device=agent_mask7.device)
                    if not mask7.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask7 = (mask7.clone()).sum(1).eq(0)
                    if visit_mask7.any():
                        visit_idx_mask7 = visit_mask7.nonzero().squeeze()
                        mask7[visit_idx_mask7, 0] = 1
                        mask7[visit_idx_mask7, 1:] = 0
                if ag_id == 8:
                    mask8_start, agent_mask8_start = self.mask_start(mask8, dynamic8, up_station, tw_mask, agent_mask8)
                    mask8 = torch.as_tensor(mask8_start.clone().data, device=mask8.device)
                    agent_mask8 = torch.as_tensor(agent_mask8_start.clone().data, device=agent_mask8.device)
                    if not mask8.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask8 = (mask8.clone()).sum(1).eq(0)
                    if visit_mask8.any():
                        visit_idx_mask8 = visit_mask8.nonzero().squeeze()
                        mask8[visit_idx_mask8, 0] = 1
                        mask8[visit_idx_mask8, 1:] = 0
                if ag_id == 9:
                    mask9_start, agent_mask9_start = self.mask_start(mask9, dynamic9, up_station, tw_mask, agent_mask9)
                    mask9 = torch.as_tensor(mask9_start.clone().data, device=mask9.device)
                    agent_mask9 = torch.as_tensor(agent_mask9_start.clone().data, device=agent_mask9.device)
                    if not mask9.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask9 = (mask9.clone()).sum(1).eq(0)
                    if visit_mask9.any():
                        visit_idx_mask9 = visit_mask9.nonzero().squeeze()
                        mask9[visit_idx_mask9, 0] = 1
                        mask9[visit_idx_mask9, 1:] = 0
                if ag_id == 10:
                    mask10_start, agent_mask10_start = self.mask_start(mask10, dynamic10, up_station, tw_mask, agent_mask10)
                    mask10 = torch.as_tensor(mask10_start.clone().data, device=mask10.device)
                    agent_mask10 = torch.as_tensor(agent_mask10_start.clone().data, device=agent_mask10.device)
                    if not mask10.byte().any():
                        decision_agent_id.remove(ag_id)
                    visit_mask10 = (mask10.clone()).sum(1).eq(0)
                    if visit_mask10.any():
                        visit_idx_mask10 = visit_mask10.nonzero().squeeze()
                        mask10[visit_idx_mask10, 0] = 1
                        mask10[visit_idx_mask10, 1:] = 0
            for a_n in decision_agent_id:
                if a_n == 1:
                    decision_mask_tensor1 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden1 = self.agent_decoder1(decoder_input1)
                    probs1, last_hh1 = self.agent_pointer1(static_hidden, dynamic_hidden1, decoder_hidden1, last_hh1)
                    probs1 = F.softmax(probs1 + mask1.log(), dim=1)
                    if self.training:
                        m1 = torch.distributions.Categorical(probs1)  # Sampling
                        ptr1 = m1.sample()
                        while not torch.gather(mask1, 1, ptr1.data.unsqueeze(1)).byte().all():
                            ptr1 = m1.sample()
                        logp1 = m1.log_prob(ptr1)
                        ptr1 = ptr1 * decision_mask_tensor1.clone()
                        logp1 = logp1 * decision_mask_tensor1.clone()
                    else:
                        prob1, ptr1 = torch.max(probs1, 1)  # Greedy
                        ptr1 = ptr1 * decision_mask_tensor1.clone()
                        logp1 = prob1.log()

                    constraint_utw1 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_1_1, line_stop_tw1, tw_mask_tw1 = self.update_tw(dynamic1, ptr1.data, constraint_utw1, a_n, tw_mask)
                    record1_cl1_1 = constraint_1_1[0].clone()
                    record2_cl1_1 = constraint_1_1[1].clone()
                    record3_cl1_1 = constraint_1_1[2].clone()
                    record1 = torch.as_tensor(record1_cl1_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl1_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl1_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw1.clone().data, device=tw_mask.device)

                    if self.update_fn is not None:
                        constraint_ufn1 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic1, constraint_1_2 = self.update_fn(dynamic1, ptr1.data, constraint_ufn1, static,
                                                                  up_station, travel_time_G, all_station,
                                                                  tour_idx_dict[a_n], line_stop_tw1)
                        record1_cl1_2 = constraint_1_2[0].clone()
                        record2_cl1_2 = constraint_1_2[1].clone()
                        record3_cl1_2 = constraint_1_2[2].clone()
                        record1 = torch.as_tensor(record1_cl1_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl1_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl1_2.clone().data, device=record3.device)
                        '''Update observation information for the agent'''
                        dynamic_hidden1 = self.agent_dynamic_encoder1(dynamic1)
                    dynamic2_wbl1 = dynamic2.clone()
                    dynamic3_wbl1 = dynamic3.clone()
                    dynamic4_wbl1 = dynamic4.clone()
                    dynamic5_wbl1 = dynamic5.clone()
                    dynamic6_wbl1 = dynamic6.clone()
                    dynamic7_wbl1 = dynamic7.clone()
                    dynamic8_wbl1 = dynamic8.clone()
                    dynamic9_wbl1 = dynamic9.clone()
                    dynamic10_wbl1 = dynamic10.clone()
                    dynamic2_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl1[:, 1:4, 0:len(up_station)] = dynamic1[:, 1:4, 0:len(up_station)].clone()
                    dynamic2 = torch.as_tensor(dynamic2_wbl1.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl1.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl1.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl1.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl1.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl1.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl1.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl1.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl1.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr1.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic1[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp1.unsqueeze(1))
                    tour_idx[a_n].append(ptr1.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr1.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr1.data[ns1].item())
                    if self.mask_fn is not None:
                        '''Update mask information for the agent'''
                        mask1_fn, agent_mask1_fn = self.mask_fn(mask1, dynamic1, agent_mask1, ptr1.data)
                        mask1 = torch.as_tensor(mask1_fn.clone().data, device=mask1.device)
                        agent_mask1 = torch.as_tensor(agent_mask1_fn.clone().data, device=agent_mask1.device)
                    # Update the decoder input for each agent
                    decoder_input1 = torch.gather(static, 2, ptr1.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 2:
                    decision_mask_tensor2 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden2 = self.agent_decoder2(decoder_input2)
                    probs2, last_hh2 = self.agent_pointer2(static_hidden, dynamic_hidden2, decoder_hidden2, last_hh2)
                    probs2 = F.softmax(probs2 + mask2.log(), dim=1)
                    if self.training:
                        m2 = torch.distributions.Categorical(probs2)
                        ptr2 = m2.sample()
                        while not torch.gather(mask2, 1, ptr2.data.unsqueeze(1)).byte().all():
                            ptr2 = m2.sample()
                        logp2 = m2.log_prob(ptr2)
                        ptr2 = ptr2 * decision_mask_tensor2.clone()
                        logp2 = logp2 * decision_mask_tensor2.clone()
                    else:
                        prob2, ptr2 = torch.max(probs2, 1)
                        ptr2 = ptr2 * decision_mask_tensor2.clone()
                        logp2 = prob2.log()

                    constraint_utw2 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_2_1, line_stop_tw2, tw_mask_tw2 = self.update_tw(dynamic2, ptr2.data, constraint_utw2,
                                                                                a_n, tw_mask)
                    record1_cl2_1 = constraint_2_1[0].clone()
                    record2_cl2_1 = constraint_2_1[1].clone()
                    record3_cl2_1 = constraint_2_1[2].clone()
                    record1 = torch.as_tensor(record1_cl2_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl2_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl2_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw2.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn2 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic2, constraint_2_2 = self.update_fn(dynamic2, ptr2.data, constraint_ufn2,
                                                                  static, up_station, travel_time_G,
                                                                  all_station, tour_idx_dict[a_n], line_stop_tw2)
                        record1_cl2_2 = constraint_2_2[0].clone()
                        record2_cl2_2 = constraint_2_2[1].clone()
                        record3_cl2_2 = constraint_2_2[2].clone()
                        record1 = torch.as_tensor(record1_cl2_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl2_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl2_2.clone().data, device=record3.device)
                        '''Update observation information for the agent'''
                        dynamic_hidden2 = self.agent_dynamic_encoder2(dynamic2)
                    dynamic1_wbl2 = dynamic1.clone()
                    dynamic3_wbl2 = dynamic3.clone()
                    dynamic4_wbl2 = dynamic4.clone()
                    dynamic5_wbl2 = dynamic5.clone()
                    dynamic6_wbl2 = dynamic6.clone()
                    dynamic7_wbl2 = dynamic7.clone()
                    dynamic8_wbl2 = dynamic8.clone()
                    dynamic9_wbl2 = dynamic9.clone()
                    dynamic10_wbl2 = dynamic10.clone()
                    dynamic1_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl2[:, 1:4, 0:len(up_station)] = dynamic2[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl2.data, device=dynamic1.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl2.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl2.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl2.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl2.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl2.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl2.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl2.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl2.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr2.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic2[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp2.unsqueeze(1))
                    tour_idx[a_n].append(ptr2.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr2.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr2.data[ns1].item())
                    if self.mask_fn is not None:
                        '''Update mask information for the agent'''
                        mask2_fn, agent_mask2_fn = self.mask_fn(mask2, dynamic2, agent_mask2, ptr2.data)
                        mask2 = torch.as_tensor(mask2_fn.clone().data, device=mask2.device)
                        agent_mask2 = torch.as_tensor(agent_mask2_fn.clone().data, device=agent_mask2.device)
                    decoder_input2 = torch.gather(static, 2, ptr2.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 3:
                    decision_mask_tensor3 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden3 = self.agent_decoder3(decoder_input3)
                    probs3, last_hh3 = self.agent_pointer3(static_hidden, dynamic_hidden3, decoder_hidden3, last_hh3)
                    probs3 = F.softmax(probs3 + mask3.log(), dim=1)
                    if self.training:
                        m3 = torch.distributions.Categorical(probs3)
                        ptr3 = m3.sample()
                        while not torch.gather(mask3, 1, ptr3.data.unsqueeze(1)).byte().all():
                            ptr3 = m3.sample()
                        logp3 = m3.log_prob(ptr3)
                        ptr3 = ptr3 * decision_mask_tensor3.clone()
                        logp3 = logp3 * decision_mask_tensor3.clone()
                    else:
                        prob3, ptr3 = torch.max(probs3, 1)
                        ptr3 = ptr3 * decision_mask_tensor3.clone()
                        logp3 = prob3.log()

                    constraint_utw3 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_3_1, line_stop_tw3, tw_mask_tw3 = self.update_tw(dynamic3, ptr3.data, constraint_utw3, a_n, tw_mask)
                    record1_cl3_1 = constraint_3_1[0].clone()
                    record2_cl3_1 = constraint_3_1[1].clone()
                    record3_cl3_1 = constraint_3_1[2].clone()
                    record1 = torch.as_tensor(record1_cl3_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl3_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl3_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw3.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn3 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic3, constraint_3_2 = self.update_fn(dynamic3, ptr3.data, constraint_ufn3, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw3)
                        record1_cl3_2 = constraint_3_2[0].clone()
                        record2_cl3_2 = constraint_3_2[1].clone()
                        record3_cl3_2 = constraint_3_2[2].clone()
                        record1 = torch.as_tensor(record1_cl3_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl3_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl3_2.clone().data, device=record3.device)
                        '''Update observation information for the agent'''
                        dynamic_hidden3 = self.agent_dynamic_encoder3(dynamic3)
                    dynamic1_wbl3 = dynamic1.clone()
                    dynamic2_wbl3 = dynamic2.clone()
                    dynamic4_wbl3 = dynamic4.clone()
                    dynamic5_wbl3 = dynamic5.clone()
                    dynamic6_wbl3 = dynamic6.clone()
                    dynamic7_wbl3 = dynamic7.clone()
                    dynamic8_wbl3 = dynamic8.clone()
                    dynamic9_wbl3 = dynamic9.clone()
                    dynamic10_wbl3 = dynamic10.clone()
                    dynamic1_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl3[:, 1:4, 0:len(up_station)] = dynamic3[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl3.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl3.data, device=dynamic2.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl3.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl3.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl3.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl3.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl3.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl3.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl3.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr3.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic3[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp3.unsqueeze(1))
                    tour_idx[a_n].append(ptr3.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr3.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr3.data[ns1].item())
                    if self.mask_fn is not None:
                        '''Update mask information for the agent'''
                        mask3_fn, agent_mask3_fn = self.mask_fn(mask3, dynamic3, agent_mask3, ptr3.data)
                        mask3 = torch.as_tensor(mask3_fn.clone().data, device=mask3.device)
                        agent_mask3 = torch.as_tensor(agent_mask3_fn.clone().data, device=agent_mask3.device)
                    decoder_input3 = torch.gather(static, 2, ptr3.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 4:
                    decision_mask_tensor4 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden4 = self.agent_decoder4(decoder_input4)
                    probs4, last_hh4 = self.agent_pointer4(static_hidden, dynamic_hidden4, decoder_hidden4, last_hh4)
                    probs4 = F.softmax(probs4 + mask4.log(), dim=1)
                    if self.training:
                        m4 = torch.distributions.Categorical(probs4)
                        ptr4 = m4.sample()
                        while not torch.gather(mask4, 1, ptr4.data.unsqueeze(1)).byte().all():
                            ptr4 = m4.sample()
                        logp4 = m4.log_prob(ptr4)
                        ptr4 = ptr4 * decision_mask_tensor4.clone()
                        logp4 = logp4 * decision_mask_tensor4.clone()
                    else:
                        prob4, ptr4 = torch.max(probs4, 1)
                        ptr4 = ptr4 * decision_mask_tensor4.clone()
                        logp4 = prob4.log()
                    constraint_utw4 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_4_1, line_stop_tw4, tw_mask_tw4 = self.update_tw(dynamic4, ptr4.data, constraint_utw4, a_n, tw_mask)
                    record1_cl4_1 = constraint_4_1[0].clone()
                    record2_cl4_1 = constraint_4_1[1].clone()
                    record3_cl4_1 = constraint_4_1[2].clone()
                    record1 = torch.as_tensor(record1_cl4_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl4_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl4_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw4.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn4 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic4, constraint_4_2 = self.update_fn(dynamic4, ptr4.data, constraint_ufn4, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw4)
                        record1_cl4_2 = constraint_4_2[0].clone()
                        record2_cl4_2 = constraint_4_2[1].clone()
                        record3_cl4_2 = constraint_4_2[2].clone()
                        record1 = torch.as_tensor(record1_cl4_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl4_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl4_2.clone().data, device=record3.device)
                        dynamic_hidden4 = self.agent_dynamic_encoder4(dynamic4)
                    dynamic1_wbl4 = dynamic1.clone()
                    dynamic2_wbl4 = dynamic2.clone()
                    dynamic3_wbl4 = dynamic3.clone()
                    dynamic5_wbl4 = dynamic5.clone()
                    dynamic6_wbl4 = dynamic6.clone()
                    dynamic7_wbl4 = dynamic7.clone()
                    dynamic8_wbl4 = dynamic8.clone()
                    dynamic9_wbl4 = dynamic9.clone()
                    dynamic10_wbl4 = dynamic10.clone()
                    dynamic1_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl4[:, 1:4, 0:len(up_station)] = dynamic4[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl4.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl4.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl4.data, device=dynamic3.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl4.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl4.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl4.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl4.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl4.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl4.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr4.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic4[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp4.unsqueeze(1))
                    tour_idx[a_n].append(ptr4.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr4.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr4.data[ns1].item())
                    if self.mask_fn is not None:
                        mask4_fn, agent_mask4_fn = self.mask_fn(mask4, dynamic4, agent_mask4, ptr4.data)
                        mask4 = torch.as_tensor(mask4_fn.clone().data, device=mask4.device)
                        agent_mask4 = torch.as_tensor(agent_mask4_fn.clone().data, device=agent_mask4.device)
                    decoder_input4 = torch.gather(static, 2, ptr4.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 5:
                    decision_mask_tensor5 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden5 = self.agent_decoder5(decoder_input5)
                    probs5, last_hh5 = self.agent_pointer5(static_hidden, dynamic_hidden5, decoder_hidden5, last_hh5)
                    probs5 = F.softmax(probs5 + mask5.log(), dim=1)
                    if self.training:
                        m5 = torch.distributions.Categorical(probs5)
                        ptr5 = m5.sample()
                        while not torch.gather(mask5, 1, ptr5.data.unsqueeze(1)).byte().all():
                            ptr5 = m5.sample()
                        logp5 = m5.log_prob(ptr5)
                        ptr5 = ptr5 * decision_mask_tensor5.clone()
                        logp5 = logp5 * decision_mask_tensor5.clone()
                    else:
                        prob5, ptr5 = torch.max(probs5, 1)
                        ptr5 = ptr5 * decision_mask_tensor5.clone()
                        logp5 = prob5.log()
                    constraint_utw5 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_5_1, line_stop_tw5, tw_mask_tw5 = self.update_tw(dynamic5, ptr5.data, constraint_utw5, a_n, tw_mask)
                    record1_cl5_1 = constraint_5_1[0].clone()
                    record2_cl5_1 = constraint_5_1[1].clone()
                    record3_cl5_1 = constraint_5_1[2].clone()
                    record1 = torch.as_tensor(record1_cl5_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl5_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl5_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw5.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn5 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic5, constraint_5_2 = self.update_fn(dynamic5, ptr5.data, constraint_ufn5, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw5)
                        record1_cl5_2 = constraint_5_2[0].clone()
                        record2_cl5_2 = constraint_5_2[1].clone()
                        record3_cl5_2 = constraint_5_2[2].clone()
                        record1 = torch.as_tensor(record1_cl5_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl5_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl5_2.clone().data, device=record3.device)
                        dynamic_hidden5 = self.agent_dynamic_encoder5(dynamic5)
                    dynamic1_wbl5 = dynamic1.clone()
                    dynamic2_wbl5 = dynamic2.clone()
                    dynamic3_wbl5 = dynamic3.clone()
                    dynamic4_wbl5 = dynamic4.clone()
                    dynamic6_wbl5 = dynamic6.clone()
                    dynamic7_wbl5 = dynamic7.clone()
                    dynamic8_wbl5 = dynamic8.clone()
                    dynamic9_wbl5 = dynamic9.clone()
                    dynamic10_wbl5 = dynamic10.clone()
                    dynamic1_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl5[:, 1:4, 0:len(up_station)] = dynamic5[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl5.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl5.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl5.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl5.data, device=dynamic4.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl5.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl5.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl5.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl5.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl5.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr5.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic5[ns0][10][0].clone().item(), a_n])

                    tour_logp[a_n].append(logp5.unsqueeze(1))
                    tour_idx[a_n].append(ptr5.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr5.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr5.data[ns1].item())
                    if self.mask_fn is not None:
                        mask5_fn, agent_mask5_fn = self.mask_fn(mask5, dynamic5, agent_mask5, ptr5.data)
                        mask5 = torch.as_tensor(mask5_fn.clone().data, device=mask5.device)
                        agent_mask5 = torch.as_tensor(agent_mask5_fn.clone().data, device=agent_mask5.device)
                    decoder_input5 = torch.gather(static, 2, ptr5.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 6:
                    decision_mask_tensor6 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden6 = self.agent_decoder6(decoder_input6)
                    probs6, last_hh6 = self.agent_pointer6(static_hidden, dynamic_hidden6, decoder_hidden6, last_hh6)
                    probs6 = F.softmax(probs6 + mask6.log(), dim=1)
                    if self.training:
                        m6 = torch.distributions.Categorical(probs6)
                        ptr6 = m6.sample()
                        while not torch.gather(mask6, 1, ptr6.data.unsqueeze(1)).byte().all():
                            ptr6 = m6.sample()
                        logp6 = m6.log_prob(ptr6)
                        ptr6 = ptr6 * decision_mask_tensor6.clone()
                        logp6 = logp6 * decision_mask_tensor6.clone()
                    else:
                        prob6, ptr6 = torch.max(probs6, 1)
                        ptr6 = ptr6 * decision_mask_tensor6.clone()
                        logp6 = prob6.log()
                    constraint_utw6 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_6_1, line_stop_tw6, tw_mask_tw6 = self.update_tw(dynamic6, ptr6.data, constraint_utw6, a_n, tw_mask)
                    record1_cl6_1 = constraint_6_1[0].clone()
                    record2_cl6_1 = constraint_6_1[1].clone()
                    record3_cl6_1 = constraint_6_1[2].clone()
                    record1 = torch.as_tensor(record1_cl6_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl6_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl6_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw6.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn6 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic6, constraint_6_2 = self.update_fn(dynamic6, ptr6.data, constraint_ufn6, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw6)
                        record1_cl6_2 = constraint_6_2[0].clone()
                        record2_cl6_2 = constraint_6_2[1].clone()
                        record3_cl6_2 = constraint_6_2[2].clone()
                        record1 = torch.as_tensor(record1_cl6_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl6_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl6_2.clone().data, device=record3.device)
                        dynamic_hidden6 = self.agent_dynamic_encoder6(dynamic6)
                    dynamic1_wbl6 = dynamic1.clone()
                    dynamic2_wbl6 = dynamic2.clone()
                    dynamic3_wbl6 = dynamic3.clone()
                    dynamic4_wbl6 = dynamic4.clone()
                    dynamic5_wbl6 = dynamic5.clone()
                    dynamic7_wbl6 = dynamic7.clone()
                    dynamic8_wbl6 = dynamic8.clone()
                    dynamic9_wbl6 = dynamic9.clone()
                    dynamic10_wbl6 = dynamic10.clone()
                    dynamic1_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl6[:, 1:4, 0:len(up_station)] = dynamic6[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl6.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl6.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl6.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl6.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl6.data, device=dynamic5.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl6.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl6.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl6.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl6.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr6.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic6[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp6.unsqueeze(1))
                    tour_idx[a_n].append(ptr6.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr6.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr6.data[ns1].item())
                    if self.mask_fn is not None:
                        mask6_fn, agent_mask6_fn = self.mask_fn(mask6, dynamic6, agent_mask6, ptr6.data)
                        mask6 = torch.as_tensor(mask6_fn.clone().data, device=mask6.device)
                        agent_mask6 = torch.as_tensor(agent_mask6_fn.clone().data, device=agent_mask6.device)
                    decoder_input6 = torch.gather(static, 2, ptr6.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 7:
                    decision_mask_tensor7 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden7 = self.agent_decoder7(decoder_input7)
                    probs7, last_hh7 = self.agent_pointer7(static_hidden, dynamic_hidden7, decoder_hidden7, last_hh7)
                    probs7 = F.softmax(probs7 + mask7.log(), dim=1)
                    if self.training:
                        m7 = torch.distributions.Categorical(probs7)
                        ptr7 = m7.sample()
                        while not torch.gather(mask7, 1, ptr7.data.unsqueeze(1)).byte().all():
                            ptr7 = m7.sample()
                        logp7 = m7.log_prob(ptr7)
                        ptr7 = ptr7 * decision_mask_tensor7.clone()
                        logp7 = logp7 * decision_mask_tensor7.clone()
                    else:
                        prob7, ptr7 = torch.max(probs7, 1)
                        ptr7 = ptr7 * decision_mask_tensor7.clone()
                        logp7 = prob7.log()
                    constraint_utw7 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_7_1, line_stop_tw7, tw_mask_tw7 = self.update_tw(dynamic7, ptr7.data, constraint_utw7, a_n, tw_mask)
                    record1_cl7_1 = constraint_7_1[0].clone()
                    record2_cl7_1 = constraint_7_1[1].clone()
                    record3_cl7_1 = constraint_7_1[2].clone()
                    record1 = torch.as_tensor(record1_cl7_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl7_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl7_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw7.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn7 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic7, constraint_7_2 = self.update_fn(dynamic7, ptr7.data, constraint_ufn7, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw7)
                        record1_cl7_2 = constraint_7_2[0].clone()
                        record2_cl7_2 = constraint_7_2[1].clone()
                        record3_cl7_2 = constraint_7_2[2].clone()
                        record1 = torch.as_tensor(record1_cl7_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl7_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl7_2.clone().data, device=record3.device)
                        dynamic_hidden7 = self.agent_dynamic_encoder7(dynamic7)
                    dynamic1_wbl7 = dynamic1.clone()
                    dynamic2_wbl7 = dynamic2.clone()
                    dynamic3_wbl7 = dynamic3.clone()
                    dynamic4_wbl7 = dynamic4.clone()
                    dynamic5_wbl7 = dynamic5.clone()
                    dynamic6_wbl7 = dynamic6.clone()
                    dynamic8_wbl7 = dynamic8.clone()
                    dynamic9_wbl7 = dynamic9.clone()
                    dynamic10_wbl7 = dynamic10.clone()
                    dynamic1_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl7[:, 1:4, 0:len(up_station)] = dynamic7[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl7.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl7.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl7.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl7.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl7.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl7.data, device=dynamic6.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl7.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl7.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl7.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr7.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic7[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp7.unsqueeze(1))
                    tour_idx[a_n].append(ptr7.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr7.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr7.data[ns1].item())
                    if self.mask_fn is not None:
                        mask7_fn, agent_mask7_fn = self.mask_fn(mask7, dynamic7, agent_mask7, ptr7.data)
                        mask7 = torch.as_tensor(mask7_fn.clone().data, device=mask7.device)
                        agent_mask7 = torch.as_tensor(agent_mask7_fn.clone().data, device=agent_mask7.device)
                    decoder_input7 = torch.gather(static, 2, ptr7.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 8:
                    decision_mask_tensor8 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden8 = self.agent_decoder8(decoder_input8)
                    probs8, last_hh8 = self.agent_pointer8(static_hidden, dynamic_hidden8, decoder_hidden8, last_hh8)
                    probs8 = F.softmax(probs8 + mask8.log(), dim=1)
                    if self.training:
                        m8 = torch.distributions.Categorical(probs8)
                        ptr8 = m8.sample()
                        while not torch.gather(mask8, 1, ptr8.data.unsqueeze(1)).byte().all():
                            ptr8 = m8.sample()
                        logp8 = m8.log_prob(ptr8)
                        ptr8 = ptr8 * decision_mask_tensor8.clone()
                        logp8 = logp8 * decision_mask_tensor8.clone()
                    else:
                        prob8, ptr8 = torch.max(probs8, 1)
                        ptr8 = ptr8 * decision_mask_tensor8.clone()
                        logp8 = prob8.log()
                    constraint_utw8 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_8_1, line_stop_tw8, tw_mask_tw8 = self.update_tw(dynamic8, ptr8.data, constraint_utw8, a_n, tw_mask)
                    record1_cl8_1 = constraint_8_1[0].clone()
                    record2_cl8_1 = constraint_8_1[1].clone()
                    record3_cl8_1 = constraint_8_1[2].clone()
                    record1 = torch.as_tensor(record1_cl8_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl8_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl8_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw8.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn8 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic8, constraint_8_2 = self.update_fn(dynamic8, ptr8.data, constraint_ufn8, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw8)
                        record1_cl8_2 = constraint_8_2[0].clone()
                        record2_cl8_2 = constraint_8_2[1].clone()
                        record3_cl8_2 = constraint_8_2[2].clone()
                        record1 = torch.as_tensor(record1_cl8_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl8_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl8_2.clone().data, device=record3.device)
                        dynamic_hidden8 = self.agent_dynamic_encoder8(dynamic8)
                    dynamic1_wbl8 = dynamic1.clone()
                    dynamic2_wbl8 = dynamic2.clone()
                    dynamic3_wbl8 = dynamic3.clone()
                    dynamic4_wbl8 = dynamic4.clone()
                    dynamic5_wbl8 = dynamic5.clone()
                    dynamic6_wbl8 = dynamic6.clone()
                    dynamic7_wbl8 = dynamic7.clone()
                    dynamic9_wbl8 = dynamic9.clone()
                    dynamic10_wbl8 = dynamic10.clone()
                    dynamic1_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl8[:, 1:4, 0:len(up_station)] = dynamic8[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl8.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl8.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl8.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl8.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl8.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl8.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl8.data, device=dynamic7.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl8.data, device=dynamic9.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl8.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr8.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic8[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp8.unsqueeze(1))
                    tour_idx[a_n].append(ptr8.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr8.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr8.data[ns1].item())
                    if self.mask_fn is not None:
                        mask8_fn, agent_mask8_fn = self.mask_fn(mask8, dynamic8, agent_mask8, ptr8.data)
                        mask8 = torch.as_tensor(mask8_fn.clone().data, device=mask8.device)
                        agent_mask8 = torch.as_tensor(agent_mask8_fn.clone().data, device=agent_mask8.device)
                    decoder_input8 = torch.gather(static, 2, ptr8.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 9:
                    decision_mask_tensor9 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden9 = self.agent_decoder9(decoder_input9)
                    probs9, last_hh9 = self.agent_pointer9(static_hidden, dynamic_hidden9, decoder_hidden9, last_hh9)
                    probs9 = F.softmax(probs9 + mask9.log(), dim=1)
                    if self.training:
                        m9 = torch.distributions.Categorical(probs9)
                        ptr9 = m9.sample()
                        while not torch.gather(mask9, 1, ptr9.data.unsqueeze(1)).byte().all():
                            ptr9 = m9.sample()
                        logp9 = m9.log_prob(ptr9)
                        ptr9 = ptr9 * decision_mask_tensor9.clone()
                        logp9 = logp9 * decision_mask_tensor9.clone()
                    else:
                        prob9, ptr9 = torch.max(probs9, 1)
                        ptr9 = ptr9 * decision_mask_tensor9.clone()
                        logp9 = prob9.log()

                    constraint_utw9 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_9_1, line_stop_tw9, tw_mask_tw9 = self.update_tw(dynamic9, ptr9.data, constraint_utw9, a_n, tw_mask)
                    record1_cl9_1 = constraint_9_1[0].clone()
                    record2_cl9_1 = constraint_9_1[1].clone()
                    record3_cl9_1 = constraint_9_1[2].clone()
                    record1 = torch.as_tensor(record1_cl9_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl9_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl9_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw9.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn9 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic9, constraint_9_2 = self.update_fn(dynamic9, ptr9.data, constraint_ufn9, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw9)
                        record1_cl9_2 = constraint_9_2[0].clone()
                        record2_cl9_2 = constraint_9_2[1].clone()
                        record3_cl9_2 = constraint_9_2[2].clone()
                        record1 = torch.as_tensor(record1_cl9_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl9_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl9_2.clone().data, device=record3.device)
                        dynamic_hidden9 = self.agent_dynamic_encoder9(dynamic9)
                    dynamic1_wbl9 = dynamic1.clone()
                    dynamic2_wbl9 = dynamic2.clone()
                    dynamic3_wbl9 = dynamic3.clone()
                    dynamic4_wbl9 = dynamic4.clone()
                    dynamic5_wbl9 = dynamic5.clone()
                    dynamic6_wbl9 = dynamic6.clone()
                    dynamic7_wbl9 = dynamic7.clone()
                    dynamic8_wbl9 = dynamic8.clone()
                    dynamic10_wbl9 = dynamic10.clone()
                    dynamic1_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic10_wbl9[:, 1:4, 0:len(up_station)] = dynamic9[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl9.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl9.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl9.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl9.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl9.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl9.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl9.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl9.data, device=dynamic8.device)
                    dynamic10 = torch.as_tensor(dynamic10_wbl9.data, device=dynamic10.device)
                    for ns0 in range(len(decision_list)):
                        if ptr9.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic9[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp9.unsqueeze(1))
                    tour_idx[a_n].append(ptr9.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr9.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr9.data[ns1].item())
                    if self.mask_fn is not None:
                        mask9_fn, agent_mask9_fn = self.mask_fn(mask9, dynamic9, agent_mask9, ptr9.data)
                        mask9 = torch.as_tensor(mask9_fn.clone().data, device=mask9.device)
                        agent_mask9 = torch.as_tensor(agent_mask9_fn.clone().data, device=agent_mask9.device)
                    decoder_input9 = torch.gather(static, 2, ptr9.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                if a_n == 10:
                    decision_mask_tensor10 = torch.tensor(decision_mask_dict[a_n]).clone().to(device)
                    decoder_hidden10 = self.agent_decoder10(decoder_input10)
                    probs10, last_hh10 = self.agent_pointer10(static_hidden, dynamic_hidden10, decoder_hidden10, last_hh10)
                    probs10 = F.softmax(probs10 + mask10.log(), dim=1)
                    if self.training:
                        m10 = torch.distributions.Categorical(probs10)
                        ptr10 = m10.sample()
                        while not torch.gather(mask10, 1, ptr10.data.unsqueeze(1)).byte().all():
                            ptr10 = m10.sample()
                        logp10 = m10.log_prob(ptr10)
                        ptr10 = ptr10 * decision_mask_tensor10.clone()
                        logp10 = logp10 * decision_mask_tensor10.clone()
                    else:
                        prob10, ptr10 = torch.max(probs10, 1)
                        ptr10 = ptr10 * decision_mask_tensor10.clone()
                        logp10 = prob10.log()
                    constraint_utw10 = [record1.clone(), record2.clone(), record3.clone()]
                    constraint_10_1, line_stop_tw10, tw_mask_tw10 = self.update_tw(dynamic10, ptr10.data, constraint_utw10, a_n, tw_mask)
                    record1_cl10_1 = constraint_10_1[0].clone()
                    record2_cl10_1 = constraint_10_1[1].clone()
                    record3_cl10_1 = constraint_10_1[2].clone()
                    record1 = torch.as_tensor(record1_cl10_1.clone().data, device=record1.device)
                    record2 = torch.as_tensor(record2_cl10_1.clone().data, device=record2.device)
                    record3 = torch.as_tensor(record3_cl10_1.clone().data, device=record3.device)
                    tw_mask = torch.as_tensor(tw_mask_tw10.clone().data, device=tw_mask.device)
                    if self.update_fn is not None:
                        constraint_ufn10 = [record1.clone(), record2.clone(), record3.clone()]
                        dynamic10, constraint_10_2 = self.update_fn(dynamic10, ptr10.data, constraint_ufn10, static, up_station,
                                                                  travel_time_G, all_station, tour_idx_dict[a_n], line_stop_tw10)
                        record1_cl10_2 = constraint_10_2[0].clone()
                        record2_cl10_2 = constraint_10_2[1].clone()
                        record3_cl10_2 = constraint_10_2[2].clone()
                        record1 = torch.as_tensor(record1_cl10_2.clone().data, device=record1.device)
                        record2 = torch.as_tensor(record2_cl10_2.clone().data, device=record2.device)
                        record3 = torch.as_tensor(record3_cl10_2.clone().data, device=record3.device)
                        dynamic_hidden10 = self.agent_dynamic_encoder10(dynamic10)
                    dynamic1_wbl10 = dynamic1.clone()
                    dynamic2_wbl10 = dynamic2.clone()
                    dynamic3_wbl10 = dynamic3.clone()
                    dynamic4_wbl10 = dynamic4.clone()
                    dynamic5_wbl10 = dynamic5.clone()
                    dynamic6_wbl10 = dynamic6.clone()
                    dynamic7_wbl10 = dynamic7.clone()
                    dynamic8_wbl10 = dynamic8.clone()
                    dynamic9_wbl10 = dynamic9.clone()
                    dynamic1_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic2_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic3_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic4_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic5_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic6_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic7_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic8_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic9_wbl10[:, 1:4, 0:len(up_station)] = dynamic10[:, 1:4, 0:len(up_station)].clone()
                    dynamic1 = torch.as_tensor(dynamic1_wbl10.data, device=dynamic1.device)
                    dynamic2 = torch.as_tensor(dynamic2_wbl10.data, device=dynamic2.device)
                    dynamic3 = torch.as_tensor(dynamic3_wbl10.data, device=dynamic3.device)
                    dynamic4 = torch.as_tensor(dynamic4_wbl10.data, device=dynamic4.device)
                    dynamic5 = torch.as_tensor(dynamic5_wbl10.data, device=dynamic5.device)
                    dynamic6 = torch.as_tensor(dynamic6_wbl10.data, device=dynamic6.device)
                    dynamic7 = torch.as_tensor(dynamic7_wbl10.data, device=dynamic7.device)
                    dynamic8 = torch.as_tensor(dynamic8_wbl10.data, device=dynamic8.device)
                    dynamic9 = torch.as_tensor(dynamic9_wbl10.data, device=dynamic9.device)
                    for ns0 in range(len(decision_list)):
                        if ptr10.data[ns0].item() != 0:
                            decision_list[ns0].append([dynamic10[ns0][10][0].clone().item(), a_n])
                    tour_logp[a_n].append(logp10.unsqueeze(1))
                    tour_idx[a_n].append(ptr10.data.unsqueeze(1))
                    for ns1 in range(len(decision_list)):
                        if ptr10.data[ns1].item() != 0:
                            tour_idx_dict[a_n][ns1].append(ptr10.data[ns1].item())
                    if self.mask_fn is not None:
                        mask10_fn, agent_mask10_fn = self.mask_fn(mask10, dynamic10, agent_mask10, ptr10.data)
                        mask10 = torch.as_tensor(mask10_fn.clone().data, device=mask10.device)
                        agent_mask10 = torch.as_tensor(agent_mask10_fn.clone().data, device=agent_mask10.device)
                    decoder_input10 = torch.gather(static, 2, ptr10.view(-1, 1, 1).expand(-1, input_size, 1)).detach()

                for ag_id in range(a_n+1, self.agent_number):
                    if ag_id == 1:
                        mask1_start, agent_mask1_start = self.mask_start(mask1, dynamic1, up_station, tw_mask, agent_mask1)
                        mask1 = torch.as_tensor(mask1_start.clone().data, device=mask1.device)
                        agent_mask1 = torch.as_tensor(agent_mask1_start.clone().data, device=agent_mask1.device)
                        visit_mask1 = (mask1.clone()).sum(1).eq(0)
                        if visit_mask1.any():
                            visit_idx_mask1 = visit_mask1.nonzero().squeeze()
                            mask1[visit_idx_mask1, 0] = 1
                            mask1[visit_idx_mask1, 1:] = 0
                    if ag_id == 2:
                        mask2_start, agent_mask2_start = self.mask_start(mask2, dynamic2, up_station, tw_mask, agent_mask2)
                        mask2 = torch.as_tensor(mask2_start.clone().data, device=mask2.device)
                        agent_mask2 = torch.as_tensor(agent_mask2_start.clone().data, device=agent_mask2.device)
                        visit_mask2 = (mask2.clone()).sum(1).eq(0)
                        if visit_mask2.any():
                            visit_idx_mask2 = visit_mask2.nonzero().squeeze()
                            mask2[visit_idx_mask2, 0] = 1
                            mask2[visit_idx_mask2, 1:] = 0
                    if ag_id == 3:
                        mask3_start, agent_mask3_start = self.mask_start(mask3, dynamic3, up_station, tw_mask, agent_mask3)
                        mask3 = torch.as_tensor(mask3_start.clone().data, device=mask3.device)
                        agent_mask3 = torch.as_tensor(agent_mask3_start.clone().data, device=agent_mask3.device)
                        visit_mask3 = (mask3.clone()).sum(1).eq(0)
                        if visit_mask3.any():
                            visit_idx_mask3 = visit_mask3.nonzero().squeeze()
                            mask3[visit_idx_mask3, 0] = 1
                            mask3[visit_idx_mask3, 1:] = 0
                    if ag_id == 4:
                        mask4_start, agent_mask4_start = self.mask_start(mask4, dynamic4, up_station, tw_mask, agent_mask4)
                        mask4 = torch.as_tensor(mask4_start.clone().data, device=mask4.device)
                        agent_mask4 = torch.as_tensor(agent_mask4_start.clone().data, device=agent_mask4.device)
                        visit_mask4 = (mask4.clone()).sum(1).eq(0)
                        if visit_mask4.any():
                            visit_idx_mask4 = visit_mask4.nonzero().squeeze()
                            mask4[visit_idx_mask4, 0] = 1
                            mask4[visit_idx_mask4, 1:] = 0
                    if ag_id == 5:
                        mask5_start, agent_mask5_start = self.mask_start(mask5, dynamic5, up_station, tw_mask, agent_mask5)
                        mask5 = torch.as_tensor(mask5_start.clone().data, device=mask5.device)
                        agent_mask5 = torch.as_tensor(agent_mask5_start.clone().data, device=agent_mask5.device)
                        visit_mask5 = (mask5.clone()).sum(1).eq(0)
                        if visit_mask5.any():
                            visit_idx_mask5 = visit_mask5.nonzero().squeeze()
                            mask5[visit_idx_mask5, 0] = 1
                            mask5[visit_idx_mask5, 1:] = 0
                    if ag_id == 6:
                        mask6_start, agent_mask6_start = self.mask_start(mask6, dynamic6, up_station, tw_mask,
                                                                         agent_mask6)
                        mask6 = torch.as_tensor(mask6_start.clone().data, device=mask6.device)
                        agent_mask6 = torch.as_tensor(agent_mask6_start.clone().data, device=agent_mask6.device)
                        visit_mask6 = (mask6.clone()).sum(1).eq(0)
                        if visit_mask6.any():
                            visit_idx_mask6 = visit_mask6.nonzero().squeeze()
                            mask6[visit_idx_mask6, 0] = 1
                            mask6[visit_idx_mask6, 1:] = 0
                    if ag_id == 7:
                        mask7_start, agent_mask7_start = self.mask_start(mask7, dynamic7, up_station, tw_mask,
                                                                         agent_mask7)
                        mask7 = torch.as_tensor(mask7_start.clone().data, device=mask7.device)
                        agent_mask7 = torch.as_tensor(agent_mask7_start.clone().data, device=agent_mask7.device)
                        visit_mask7 = (mask7.clone()).sum(1).eq(0)
                        if visit_mask7.any():
                            visit_idx_mask7 = visit_mask7.nonzero().squeeze()
                            mask7[visit_idx_mask7, 0] = 1
                            mask7[visit_idx_mask7, 1:] = 0
                    if ag_id == 8:
                        mask8_start, agent_mask8_start = self.mask_start(mask8, dynamic8, up_station, tw_mask,
                                                                         agent_mask8)
                        mask8 = torch.as_tensor(mask8_start.clone().data, device=mask8.device)
                        agent_mask8 = torch.as_tensor(agent_mask8_start.clone().data, device=agent_mask8.device)
                        visit_mask8 = (mask8.clone()).sum(1).eq(0)
                        if visit_mask8.any():
                            visit_idx_mask8 = visit_mask8.nonzero().squeeze()
                            mask8[visit_idx_mask8, 0] = 1
                            mask8[visit_idx_mask8, 1:] = 0
                    if ag_id == 9:
                        mask9_start, agent_mask9_start = self.mask_start(mask9, dynamic9, up_station, tw_mask,
                                                                         agent_mask9)
                        mask9 = torch.as_tensor(mask9_start.clone().data, device=mask9.device)
                        agent_mask9 = torch.as_tensor(agent_mask9_start.clone().data, device=agent_mask9.device)
                        visit_mask9 = (mask9.clone()).sum(1).eq(0)
                        if visit_mask9.any():
                            visit_idx_mask9 = visit_mask9.nonzero().squeeze()
                            mask9[visit_idx_mask9, 0] = 1
                            mask9[visit_idx_mask9, 1:] = 0
                    if ag_id == 10:
                        mask10_start, agent_mask10_start = self.mask_start(mask10, dynamic10, up_station, tw_mask,
                                                                           agent_mask10)
                        mask10 = torch.as_tensor(mask10_start.clone().data, device=mask10.device)
                        agent_mask10 = torch.as_tensor(agent_mask10_start.clone().data, device=agent_mask10.device)
                        visit_mask10 = (mask10.clone()).sum(1).eq(0)
                        if visit_mask10.any():
                            visit_idx_mask10 = visit_mask10.nonzero().squeeze()
                            mask10[visit_idx_mask10, 0] = 1
                            mask10[visit_idx_mask10, 1:] = 0
            for so in range(len(decision_list)):
                list.sort(decision_list[so], key=(lambda x: [x[0]]))
        for a_id0 in range(1, self.agent_number):
            tour_idx[a_id0] = torch.cat(tour_idx[a_id0], dim=1)
            tour_logp[a_id0] = torch.cat(tour_logp[a_id0], dim=1)
        return tour_idx, tour_logp, [record1.clone(), record2.clone(), record3.clone()],\
               [dynamic1.clone(), dynamic2.clone(), dynamic3.clone(), dynamic4.clone(), dynamic5.clone(),
                dynamic6.clone(), dynamic7.clone(), dynamic8.clone(), dynamic9.clone(), dynamic10.clone()]


if __name__ == '__main__':
    raise Exception('Cannot be called from main')
