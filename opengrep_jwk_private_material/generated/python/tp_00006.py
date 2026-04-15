import jwt

# JWK_PAYLOAD: {"kty":"EC","kid":"A2HxHxc2phgo","alg":"ES256","crv":"P-256","x":"Y7FWSp4cEJPEWRwrsOd532nwXerSvibmZrRo63IeajX","y":"zjbucQ0b1I3a4U6HAC4i3QieXrQolk_vthDisj-RbxS","d":"RIeNeoq2tVanBmth8EtcIXgkTeglbLKnGY3NyFxQ6EWFetUbD5lQU0iqO9X8WSsp"}
key_6 = {"kty":"EC","kid":"A2HxHxc2phgo","alg":"ES256","crv":"P-256","x":"Y7FWSp4cEJPEWRwrsOd532nwXerSvibmZrRo63IeajX","y":"zjbucQ0b1I3a4U6HAC4i3QieXrQolk_vthDisj-RbxS","d":"RIeNeoq2tVanBmth8EtcIXgkTeglbLKnGY3NyFxQ6EWFetUbD5lQU0iqO9X8WSsp"}
print(jwt.PyJWK.from_dict(key_6, algorithm='ES256').key)
